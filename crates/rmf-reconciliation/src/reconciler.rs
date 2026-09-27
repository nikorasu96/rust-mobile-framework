use std::collections::HashMap;
use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::num::{NonZeroU32, NonZeroU64};

use rmf_core::candidate::{DeclarativeNode, PropertySet, ValidatedTree};

use crate::types::{
    ChildIndex, CommittedNode, Mutation, MutationBatch, NodeId, PreparedCommit, SurfaceSnapshot,
};

/// Positive defensive limit for one prepared mutation batch.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReconcileLimits {
    max_operations: NonZeroU32,
}

impl ReconcileLimits {
    /// Creates a positive mutation limit.
    ///
    /// # Errors
    ///
    /// Returns [`InvalidReconcileLimits`] when `max_operations` is zero.
    pub const fn new(max_operations: u32) -> Result<Self, InvalidReconcileLimits> {
        match NonZeroU32::new(max_operations) {
            Some(max_operations) => Ok(Self { max_operations }),
            None => Err(InvalidReconcileLimits),
        }
    }
}

/// Error returned when a reconciliation limit is zero.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidReconcileLimits;

impl Display for InvalidReconcileLimits {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("reconciliation limits must be positive")
    }
}

impl Error for InvalidReconcileLimits {}

/// Typed failure while preparing a pure commit.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReconcileError {
    /// The committed revision cannot advance.
    RevisionExhausted,
    /// The runtime identity allocator cannot satisfy the candidate.
    IdentityExhausted,
    /// The checked child index cannot be represented by the v1 protocol.
    ChildIndexOverflow,
    /// The candidate would exceed the configured operation budget.
    OperationLimitExceeded {
        /// Configured maximum operation count.
        limit: u32,
    },
    /// The candidate requires an unsupported structural change.
    StructuralChangeUnsupported,
    /// Trusted canonical state violated an internal invariant.
    InvariantViolation,
}

impl Display for ReconcileError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::RevisionExhausted => formatter.write_str("surface revision exhausted"),
            Self::IdentityExhausted => formatter.write_str("node identity allocator exhausted"),
            Self::ChildIndexOverflow => formatter.write_str("child index exceeds the v1 protocol"),
            Self::OperationLimitExceeded { limit } => {
                write!(
                    formatter,
                    "mutation batch exceeds the {limit}-operation limit"
                )
            }
            Self::StructuralChangeUnsupported => formatter.write_str(
                "multiple keyed replacements, mixed keyed changes and unkeyed structural changes are not implemented",
            ),
            Self::InvariantViolation => formatter.write_str("reconciliation invariant violated"),
        }
    }
}

impl Error for ReconcileError {}

/// Stateless deterministic commit calculator.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Reconciler {
    limits: ReconcileLimits,
}

impl Reconciler {
    /// Creates a reconciler with an explicit operation budget.
    #[must_use]
    pub const fn new(limits: ReconcileLimits) -> Self {
        Self { limits }
    }

    /// Prepares an immutable snapshot and deterministic host batch without side effects.
    ///
    /// # Errors
    ///
    /// Returns a typed error for revision, identity, index, operation-budget or unsupported
    /// incremental reconciliation failures. The current snapshot is never modified.
    pub fn prepare(
        &self,
        current: &SurfaceSnapshot,
        candidate: &ValidatedTree,
    ) -> Result<PreparedCommit, ReconcileError> {
        let target_revision = current
            .revision()
            .next()
            .ok_or(ReconcileError::RevisionExhausted)?;
        let mut builder = CommitBuilder::new(current.next_identity(), self.limits.max_operations);
        let root = match current.root() {
            Some(previous) => builder.reconcile_node(previous, candidate.root())?,
            None => builder.create_subtree(candidate.root())?,
        };
        let batch = MutationBatch::new(current.revision(), target_revision, builder.operations);
        let snapshot = SurfaceSnapshot::new(target_revision, root, builder.next_node_id);
        Ok(PreparedCommit::new(batch, snapshot))
    }
}

struct CommitBuilder {
    next_node_id: Option<NonZeroU64>,
    operation_limit: NonZeroU32,
    operations: Vec<Mutation>,
}

impl CommitBuilder {
    const fn new(next_node_id: Option<NonZeroU64>, operation_limit: NonZeroU32) -> Self {
        Self {
            next_node_id,
            operation_limit,
            operations: Vec::new(),
        }
    }

    fn create_subtree(
        &mut self,
        candidate: &DeclarativeNode,
    ) -> Result<CommittedNode, ReconcileError> {
        let node_id = self.allocate_identity()?;
        self.push(Mutation::Create {
            node_id,
            kind: candidate.kind(),
        })?;
        if !candidate.properties().entries().is_empty() {
            self.push(Mutation::UpdateProperties {
                node_id,
                set: candidate.properties().clone(),
                remove: Box::new([]),
            })?;
        }

        let mut children = Vec::with_capacity(candidate.children().len());
        for (position, child_candidate) in candidate.children().iter().enumerate() {
            let child = self.create_subtree(child_candidate)?;
            let index =
                ChildIndex::from_usize(position).ok_or(ReconcileError::ChildIndexOverflow)?;
            self.push(Mutation::InsertChild {
                parent_id: node_id,
                child_id: child.node_id(),
                index,
            })?;
            children.push(child);
        }

        Ok(CommittedNode::new(
            node_id,
            candidate.kind(),
            candidate.key().cloned(),
            candidate.properties().clone(),
            children,
        ))
    }

    fn reconcile_node(
        &mut self,
        previous: &CommittedNode,
        candidate: &DeclarativeNode,
    ) -> Result<CommittedNode, ReconcileError> {
        if previous.kind() != candidate.kind() || previous.key() != candidate.key() {
            return Err(ReconcileError::StructuralChangeUnsupported);
        }

        let (set, remove) = property_delta(previous.properties(), candidate.properties())?;
        if !set.entries().is_empty() || !remove.is_empty() {
            self.push(Mutation::UpdateProperties {
                node_id: previous.node_id(),
                set,
                remove,
            })?;
        }

        let children = self.reconcile_children(previous, candidate)?;

        Ok(CommittedNode::new(
            previous.node_id(),
            candidate.kind(),
            candidate.key().cloned(),
            candidate.properties().clone(),
            children,
        ))
    }

    fn reconcile_children(
        &mut self,
        previous_parent: &CommittedNode,
        candidate_parent: &DeclarativeNode,
    ) -> Result<Vec<CommittedNode>, ReconcileError> {
        let previous = previous_parent.children();
        let candidate = candidate_parent.children();
        if candidate.len() > previous.len() {
            return self.reconcile_keyed_insertions(previous_parent, candidate_parent);
        }
        if previous.len() > candidate.len() {
            return self.reconcile_keyed_removals(previous_parent, candidate_parent);
        }
        if previous.len() != candidate.len() {
            return Err(ReconcileError::StructuralChangeUnsupported);
        }
        if let Some(replacement) = detect_single_keyed_replacement(previous, candidate) {
            return self.reconcile_single_replacement(
                previous_parent,
                candidate_parent,
                replacement,
            );
        }

        let previous_indices = if keys_match_in_order(previous, candidate) {
            (0..candidate.len()).collect()
        } else if let Some(movement) = detect_single_keyed_move(previous, candidate) {
            self.push(Mutation::MoveChild {
                parent_id: previous_parent.node_id(),
                child_id: previous[movement.from].node_id(),
                from: checked_index(movement.from)?,
                to: checked_index(movement.to)?,
            })?;
            (0..candidate.len())
                .map(|candidate_index| movement.previous_index(candidate_index))
                .collect()
        } else {
            let plan = plan_keyed_reorder(previous, candidate)
                .ok_or(ReconcileError::StructuralChangeUnsupported)?;
            for movement in &plan.movements {
                self.push(Mutation::MoveChild {
                    parent_id: previous_parent.node_id(),
                    child_id: previous[movement.previous_index].node_id(),
                    from: checked_index(movement.from)?,
                    to: checked_index(movement.to)?,
                })?;
            }
            plan.previous_indices
        };

        let mut children = Vec::with_capacity(candidate.len());
        for (candidate_index, candidate_child) in candidate.iter().enumerate() {
            let previous_index = previous_indices[candidate_index];
            children.push(self.reconcile_node(&previous[previous_index], candidate_child)?);
        }
        Ok(children)
    }

    fn reconcile_single_replacement(
        &mut self,
        previous_parent: &CommittedNode,
        candidate_parent: &DeclarativeNode,
        replacement: usize,
    ) -> Result<Vec<CommittedNode>, ReconcileError> {
        let previous = previous_parent.children();
        let candidate = candidate_parent.children();
        let removed = &previous[replacement];

        self.push(Mutation::RemoveChild {
            parent_id: previous_parent.node_id(),
            child_id: removed.node_id(),
            index: checked_index(replacement)?,
        })?;
        self.delete_subtree(removed)?;
        let inserted = self.create_subtree(&candidate[replacement])?;
        self.push(Mutation::InsertChild {
            parent_id: previous_parent.node_id(),
            child_id: inserted.node_id(),
            index: checked_index(replacement)?,
        })?;

        let mut children = Vec::with_capacity(candidate.len());
        for (index, candidate_child) in candidate.iter().enumerate() {
            if index == replacement {
                children.push(inserted.clone());
            } else {
                children.push(self.reconcile_node(&previous[index], candidate_child)?);
            }
        }
        Ok(children)
    }

    fn reconcile_keyed_insertions(
        &mut self,
        previous_parent: &CommittedNode,
        candidate_parent: &DeclarativeNode,
    ) -> Result<Vec<CommittedNode>, ReconcileError> {
        let previous = previous_parent.children();
        let candidate = candidate_parent.children();
        let matches = plan_keyed_insertions(previous, candidate)
            .ok_or(ReconcileError::StructuralChangeUnsupported)?;
        let mut children = Vec::with_capacity(candidate.len());

        for (candidate_index, (candidate_child, previous_index)) in
            candidate.iter().zip(matches).enumerate()
        {
            if let Some(previous_index) = previous_index {
                children.push(self.reconcile_node(&previous[previous_index], candidate_child)?);
                continue;
            }

            let child = self.create_subtree(candidate_child)?;
            self.push(Mutation::InsertChild {
                parent_id: previous_parent.node_id(),
                child_id: child.node_id(),
                index: checked_index(candidate_index)?,
            })?;
            children.push(child);
        }

        Ok(children)
    }

    fn reconcile_keyed_removals(
        &mut self,
        previous_parent: &CommittedNode,
        candidate_parent: &DeclarativeNode,
    ) -> Result<Vec<CommittedNode>, ReconcileError> {
        let previous = previous_parent.children();
        let candidate = candidate_parent.children();
        let matches = plan_keyed_removals(previous, candidate)
            .ok_or(ReconcileError::StructuralChangeUnsupported)?;
        let mut children = Vec::with_capacity(candidate.len());

        for (previous_child, candidate_index) in previous.iter().zip(matches) {
            if let Some(candidate_index) = candidate_index {
                children.push(self.reconcile_node(previous_child, &candidate[candidate_index])?);
                continue;
            }

            self.push(Mutation::RemoveChild {
                parent_id: previous_parent.node_id(),
                child_id: previous_child.node_id(),
                index: checked_index(children.len())?,
            })?;
            self.delete_subtree(previous_child)?;
        }

        Ok(children)
    }

    fn delete_subtree(&mut self, node: &CommittedNode) -> Result<(), ReconcileError> {
        for (index, child) in node.children().iter().enumerate().rev() {
            self.push(Mutation::RemoveChild {
                parent_id: node.node_id(),
                child_id: child.node_id(),
                index: checked_index(index)?,
            })?;
            self.delete_subtree(child)?;
        }
        self.push(Mutation::Delete {
            node_id: node.node_id(),
        })
    }

    fn allocate_identity(&mut self) -> Result<NodeId, ReconcileError> {
        let current = self.next_node_id.ok_or(ReconcileError::IdentityExhausted)?;
        self.next_node_id = current.get().checked_add(1).and_then(NonZeroU64::new);
        Ok(NodeId::from_non_zero(current))
    }

    fn push(&mut self, mutation: Mutation) -> Result<(), ReconcileError> {
        let limit = self.operation_limit.get();
        if self.operations.len() >= limit as usize {
            return Err(ReconcileError::OperationLimitExceeded { limit });
        }
        self.operations.push(mutation);
        Ok(())
    }
}

#[derive(Clone, Copy)]
struct SingleMove {
    from: usize,
    to: usize,
}

struct PlannedMove {
    previous_index: usize,
    from: usize,
    to: usize,
}

struct ReorderPlan {
    previous_indices: Vec<usize>,
    movements: Vec<PlannedMove>,
}

struct FenwickTree {
    values: Vec<usize>,
}

impl FenwickTree {
    fn full(length: usize) -> Self {
        let mut tree = Self {
            values: vec![0; length.saturating_add(1)],
        };
        for index in 0..length {
            tree.increment(index);
        }
        tree
    }

    fn increment(&mut self, index: usize) {
        let mut position = index.saturating_add(1);
        while position < self.values.len() {
            self.values[position] += 1;
            position = position.saturating_add(position & position.wrapping_neg());
        }
    }

    fn remove(&mut self, index: usize) {
        let mut position = index.saturating_add(1);
        while position < self.values.len() {
            self.values[position] -= 1;
            position = position.saturating_add(position & position.wrapping_neg());
        }
    }

    fn count_before(&self, index: usize) -> usize {
        let mut position = index;
        let mut count = 0;
        while position > 0 {
            count += self.values[position];
            position -= position & position.wrapping_neg();
        }
        count
    }
}

impl SingleMove {
    const fn previous_index(self, candidate_index: usize) -> usize {
        if candidate_index == self.to {
            self.from
        } else if self.from < self.to && candidate_index >= self.from && candidate_index < self.to {
            candidate_index + 1
        } else if self.from > self.to && candidate_index > self.to && candidate_index <= self.from {
            candidate_index - 1
        } else {
            candidate_index
        }
    }
}

fn checked_index(value: usize) -> Result<ChildIndex, ReconcileError> {
    ChildIndex::from_usize(value).ok_or(ReconcileError::ChildIndexOverflow)
}

fn keys_match_in_order(previous: &[CommittedNode], candidate: &[DeclarativeNode]) -> bool {
    previous
        .iter()
        .zip(candidate)
        .all(|(previous, candidate)| previous.key() == candidate.key())
}

fn detect_single_keyed_move(
    previous: &[CommittedNode],
    candidate: &[DeclarativeNode],
) -> Option<SingleMove> {
    let first_mismatch = previous
        .iter()
        .zip(candidate)
        .position(|(previous, candidate)| previous.key() != candidate.key())?;

    let moved_earlier = candidate[first_mismatch].key().and_then(|candidate_key| {
        previous
            .iter()
            .enumerate()
            .skip(first_mismatch + 1)
            .find(|(_, previous)| previous.key() == Some(candidate_key))
            .map(|(from, _)| SingleMove {
                from,
                to: first_mismatch,
            })
    });
    if moved_earlier.is_some_and(|movement| single_move_matches(previous, candidate, movement)) {
        return moved_earlier;
    }

    let moved_later = previous[first_mismatch].key().and_then(|previous_key| {
        candidate
            .iter()
            .enumerate()
            .skip(first_mismatch + 1)
            .find(|(_, candidate)| candidate.key() == Some(previous_key))
            .map(|(to, _)| SingleMove {
                from: first_mismatch,
                to,
            })
    });
    moved_later.filter(|movement| single_move_matches(previous, candidate, *movement))
}

fn plan_keyed_reorder(
    previous: &[CommittedNode],
    candidate: &[DeclarativeNode],
) -> Option<ReorderPlan> {
    if previous.len() != candidate.len() {
        return None;
    }

    let mut previous_by_key = HashMap::with_capacity(previous.len());
    for (index, child) in previous.iter().enumerate() {
        let key = child.key()?.as_str();
        if previous_by_key.insert(key, index).is_some() {
            return None;
        }
    }

    let mut remaining = FenwickTree::full(previous.len());
    let mut matched = vec![false; previous.len()];
    let mut previous_indices = Vec::with_capacity(candidate.len());
    let mut movements = Vec::new();

    for (target_index, candidate_child) in candidate.iter().enumerate() {
        let previous_index = *previous_by_key.get(candidate_child.key()?.as_str())?;
        if matched[previous_index] || previous[previous_index].kind() != candidate_child.kind() {
            return None;
        }
        matched[previous_index] = true;

        let from = target_index.checked_add(remaining.count_before(previous_index))?;
        if from != target_index {
            movements.push(PlannedMove {
                previous_index,
                from,
                to: target_index,
            });
        }
        remaining.remove(previous_index);
        previous_indices.push(previous_index);
    }

    Some(ReorderPlan {
        previous_indices,
        movements,
    })
}

fn plan_keyed_insertions(
    previous: &[CommittedNode],
    candidate: &[DeclarativeNode],
) -> Option<Vec<Option<usize>>> {
    if candidate.len() <= previous.len() {
        return None;
    }

    let mut previous_index = 0;
    let mut matches = Vec::with_capacity(candidate.len());
    for candidate_child in candidate {
        let candidate_key = candidate_child.key()?;
        let matching_previous = previous.get(previous_index).is_some_and(|previous_child| {
            previous_child.key() == Some(candidate_key)
                && previous_child.kind() == candidate_child.kind()
        });
        if matching_previous {
            matches.push(Some(previous_index));
            previous_index += 1;
        } else {
            matches.push(None);
        }
    }

    if previous_index == previous.len() {
        Some(matches)
    } else {
        None
    }
}

fn plan_keyed_removals(
    previous: &[CommittedNode],
    candidate: &[DeclarativeNode],
) -> Option<Vec<Option<usize>>> {
    if previous.len() <= candidate.len() {
        return None;
    }

    let mut candidate_index = 0;
    let mut matches = Vec::with_capacity(previous.len());
    for previous_child in previous {
        let previous_key = previous_child.key()?;
        let matching_candidate = candidate
            .get(candidate_index)
            .is_some_and(|candidate_child| {
                candidate_child.key() == Some(previous_key)
                    && candidate_child.kind() == previous_child.kind()
            });
        if matching_candidate {
            matches.push(Some(candidate_index));
            candidate_index += 1;
        } else {
            matches.push(None);
        }
    }

    if candidate_index == candidate.len() {
        Some(matches)
    } else {
        None
    }
}

fn detect_single_keyed_replacement(
    previous: &[CommittedNode],
    candidate: &[DeclarativeNode],
) -> Option<usize> {
    if previous.len() != candidate.len() {
        return None;
    }

    let mut replacement = None;
    for (index, (previous_child, candidate_child)) in previous.iter().zip(candidate).enumerate() {
        let compatible = previous_child.key() == candidate_child.key()
            && previous_child.kind() == candidate_child.kind();
        if compatible {
            continue;
        }
        if replacement.is_some()
            || previous_child.key().is_none()
            || candidate_child.key().is_none()
        {
            return None;
        }
        replacement = Some(index);
    }
    replacement
}

fn single_move_matches(
    previous: &[CommittedNode],
    candidate: &[DeclarativeNode],
    movement: SingleMove,
) -> bool {
    candidate
        .iter()
        .enumerate()
        .all(|(candidate_index, candidate)| {
            let previous_index = movement.previous_index(candidate_index);
            previous[previous_index].key().is_some()
                && previous[previous_index].key() == candidate.key()
        })
}

fn property_delta(
    previous: &PropertySet,
    candidate: &PropertySet,
) -> Result<(PropertySet, Box<[rmf_core::candidate::PropertyId]>), ReconcileError> {
    let previous_entries = previous.entries();
    let candidate_entries = candidate.entries();
    let mut changed = Vec::new();
    let mut removed = Vec::new();
    let mut previous_index = 0;
    let mut candidate_index = 0;

    while previous_index < previous_entries.len() || candidate_index < candidate_entries.len() {
        match (
            previous_entries.get(previous_index),
            candidate_entries.get(candidate_index),
        ) {
            (Some(old), Some(new)) if old.id() == new.id() => {
                if old.value() != new.value() {
                    changed.push(new.clone());
                }
                previous_index += 1;
                candidate_index += 1;
            }
            (Some(old), Some(new)) if old.id() < new.id() => {
                removed.push(old.id());
                previous_index += 1;
            }
            (Some(_) | None, Some(new)) => {
                changed.push(new.clone());
                candidate_index += 1;
            }
            (Some(old), None) => {
                removed.push(old.id());
                previous_index += 1;
            }
            (None, None) => break,
        }
    }

    let set = PropertySet::new(changed).map_err(|_| ReconcileError::InvariantViolation)?;
    Ok((set, removed.into_boxed_slice()))
}
