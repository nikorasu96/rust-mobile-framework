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
    /// The candidate changes tree structure, which is outside the stable-tree increment.
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
            Self::StructuralChangeUnsupported => formatter
                .write_str("structural insert, removal, replacement or reorder is not implemented"),
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
            Some(previous) => builder.reconcile_stable(previous, candidate.root())?,
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

    fn reconcile_stable(
        &mut self,
        previous: &CommittedNode,
        candidate: &DeclarativeNode,
    ) -> Result<CommittedNode, ReconcileError> {
        if previous.kind() != candidate.kind()
            || previous.key() != candidate.key()
            || previous.children().len() != candidate.children().len()
        {
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

        let mut children = Vec::with_capacity(candidate.children().len());
        for (previous_child, candidate_child) in
            previous.children().iter().zip(candidate.children().iter())
        {
            children.push(self.reconcile_stable(previous_child, candidate_child)?);
        }

        Ok(CommittedNode::new(
            previous.node_id(),
            candidate.kind(),
            candidate.key().cloned(),
            candidate.properties().clone(),
            children,
        ))
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
            (Some(_), Some(new)) | (None, Some(new)) => {
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
