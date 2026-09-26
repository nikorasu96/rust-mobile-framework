//! Atomic in-memory host adapter for committed mutation batches.

use std::collections::{BTreeMap, BTreeSet};
use std::convert::Infallible;
use std::error::Error;
use std::fmt::{self, Display, Formatter};

use rmf_core::candidate::{ComponentKind, PropertyId, PropertyValue};
use rmf_reconciliation::{CommittedNode, Mutation, MutationBatch, SurfaceSnapshot};
use rmf_runtime::commit::{ApplyFailure, BatchApplier, SnapshotRemounter};

/// Safe rejection produced while validating or applying a batch to a private copy.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum HeadlessApplyError {
    /// The batch base does not match the adapter's current revision.
    StaleRevision,
    /// A mutation references a node that does not exist.
    UnknownNode,
    /// A create operation reuses a live node identity.
    DuplicateNode,
    /// A child index or attachment relation does not match current host state.
    InvalidChildRelation,
    /// A property removal names a property that is not present.
    MissingProperty,
    /// A delete targets an attached, non-empty or root node.
    NodeNotDeletable,
    /// The resulting host graph is cyclic, multiply reachable or leaves detached nodes.
    InvalidHostGraph,
}

impl Display for HeadlessApplyError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::StaleRevision => "mutation batch revision is stale",
            Self::UnknownNode => "mutation references an unknown node",
            Self::DuplicateNode => "mutation creates a duplicate node",
            Self::InvalidChildRelation => "mutation has an invalid child relation",
            Self::MissingProperty => "mutation removes an absent property",
            Self::NodeNotDeletable => "mutation deletes a node that is not detached and empty",
            Self::InvalidHostGraph => "mutation batch leaves an invalid host graph",
        };
        formatter.write_str(message)
    }
}

impl Error for HeadlessApplyError {}

#[derive(Clone, Debug, Eq, PartialEq)]
struct HostNode {
    kind: ComponentKind,
    properties: BTreeMap<PropertyId, PropertyValue>,
    parent: Option<u64>,
    children: Vec<u64>,
}

impl HostNode {
    fn empty(kind: ComponentKind) -> Self {
        Self {
            kind,
            properties: BTreeMap::new(),
            parent: None,
            children: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
struct HostState {
    revision: u64,
    root: Option<u64>,
    nodes: BTreeMap<u64, HostNode>,
}

/// Allocation-free logical metrics for the currently published headless host state.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct HeadlessHostMetrics {
    revision: u64,
    nodes: usize,
    edges: usize,
    properties: usize,
}

impl HeadlessHostMetrics {
    /// Returns the applied host revision.
    #[must_use]
    pub const fn revision(self) -> u64 {
        self.revision
    }

    /// Returns the number of live host nodes.
    #[must_use]
    pub const fn nodes(self) -> usize {
        self.nodes
    }

    /// Returns the number of parent-child edges.
    #[must_use]
    pub const fn edges(self) -> usize {
        self.edges
    }

    /// Returns the number of stored property values.
    #[must_use]
    pub const fn properties(self) -> usize {
        self.properties
    }
}

/// Deterministic host adapter that applies a whole batch atomically in memory.
///
/// Every batch is evaluated against a private state copy. Invalid input is therefore classified
/// as [`ApplyFailure::RejectedBeforeMutation`], and the observable host state remains unchanged.
#[derive(Debug, Default)]
pub struct HeadlessMutationAdapter {
    state: HostState,
}

impl HeadlessMutationAdapter {
    /// Returns the host revision after the last successful batch or remount.
    #[must_use]
    pub const fn revision(&self) -> u64 {
        self.state.revision
    }

    /// Returns the number of live host nodes.
    #[must_use]
    pub fn node_count(&self) -> usize {
        self.state.nodes.len()
    }

    /// Returns logical host-state metrics without exposing internal graph storage.
    #[must_use]
    pub fn metrics(&self) -> HeadlessHostMetrics {
        let edges = self
            .state
            .nodes
            .values()
            .map(|node| node.children.len())
            .sum();
        let properties = self
            .state
            .nodes
            .values()
            .map(|node| node.properties.len())
            .sum();
        HeadlessHostMetrics {
            revision: self.state.revision,
            nodes: self.state.nodes.len(),
            edges,
            properties,
        }
    }

    /// Returns the current root identity, if a snapshot is mounted.
    #[must_use]
    pub const fn root_id(&self) -> Option<u64> {
        self.state.root
    }

    /// Reports whether host structure, kinds and properties equal a committed snapshot.
    #[must_use]
    pub fn agrees_with(&self, snapshot: &SurfaceSnapshot) -> bool {
        if self.state.revision != snapshot.revision().get() {
            return false;
        }
        match (self.state.root, snapshot.root()) {
            (None, None) => self.state.nodes.is_empty(),
            (Some(root_id), Some(root)) if root_id == root.node_id().get() => {
                let mut visited = BTreeSet::new();
                self.node_agrees(root, None, &mut visited)
                    && visited.len() == self.state.nodes.len()
            }
            _ => false,
        }
    }

    fn node_agrees(
        &self,
        committed: &CommittedNode,
        parent: Option<u64>,
        visited: &mut BTreeSet<u64>,
    ) -> bool {
        let node_id = committed.node_id().get();
        if !visited.insert(node_id) {
            return false;
        }
        let Some(host) = self.state.nodes.get(&node_id) else {
            return false;
        };
        if host.kind != committed.kind()
            || host.parent != parent
            || host.children.len() != committed.children().len()
            || host.properties.len() != committed.properties().entries().len()
        {
            return false;
        }
        if committed
            .properties()
            .entries()
            .iter()
            .any(|entry| host.properties.get(&entry.id()) != Some(entry.value()))
        {
            return false;
        }
        host.children
            .iter()
            .zip(committed.children())
            .all(|(host_child, committed_child)| {
                *host_child == committed_child.node_id().get()
                    && self.node_agrees(committed_child, Some(node_id), visited)
            })
    }

    fn apply_to_copy(&self, batch: &MutationBatch) -> Result<HostState, HeadlessApplyError> {
        if batch.base_revision().get() != self.state.revision
            || batch.target_revision().get() != self.state.revision.saturating_add(1)
        {
            return Err(HeadlessApplyError::StaleRevision);
        }
        let mut next = self.state.clone();
        for mutation in batch.operations() {
            next.apply(mutation)?;
        }
        next.validate_graph()?;
        next.revision = batch.target_revision().get();
        Ok(next)
    }
}

impl BatchApplier for HeadlessMutationAdapter {
    type Error = HeadlessApplyError;

    fn apply_batch(&mut self, batch: &MutationBatch) -> Result<(), ApplyFailure<Self::Error>> {
        let next = self
            .apply_to_copy(batch)
            .map_err(ApplyFailure::RejectedBeforeMutation)?;
        self.state = next;
        Ok(())
    }
}

impl SnapshotRemounter for HeadlessMutationAdapter {
    type Error = Infallible;

    fn remount_snapshot(&mut self, snapshot: &SurfaceSnapshot) -> Result<(), Self::Error> {
        self.state = HostState::from_snapshot(snapshot);
        Ok(())
    }
}

impl HostState {
    fn from_snapshot(snapshot: &SurfaceSnapshot) -> Self {
        let mut state = Self {
            revision: snapshot.revision().get(),
            root: snapshot.root().map(|root| root.node_id().get()),
            nodes: BTreeMap::new(),
        };
        if let Some(root) = snapshot.root() {
            state.insert_committed(root, None);
        }
        state
    }

    fn insert_committed(&mut self, committed: &CommittedNode, parent: Option<u64>) {
        let node_id = committed.node_id().get();
        let properties = committed
            .properties()
            .entries()
            .iter()
            .map(|entry| (entry.id(), entry.value().clone()))
            .collect();
        let children = committed
            .children()
            .iter()
            .map(|child| child.node_id().get())
            .collect();
        self.nodes.insert(
            node_id,
            HostNode {
                kind: committed.kind(),
                properties,
                parent,
                children,
            },
        );
        for child in committed.children() {
            self.insert_committed(child, Some(node_id));
        }
    }

    fn apply(&mut self, mutation: &Mutation) -> Result<(), HeadlessApplyError> {
        match mutation {
            Mutation::Create { node_id, kind } => self.create(node_id.get(), *kind),
            Mutation::UpdateProperties {
                node_id,
                set,
                remove,
            } => self.update_properties(node_id.get(), set, remove),
            Mutation::InsertChild {
                parent_id,
                child_id,
                index,
            } => self.insert_child(parent_id.get(), child_id.get(), index.get()),
            Mutation::MoveChild {
                parent_id,
                child_id,
                from,
                to,
            } => self.move_child(parent_id.get(), child_id.get(), from.get(), to.get()),
            Mutation::RemoveChild {
                parent_id,
                child_id,
                index,
            } => self.remove_child(parent_id.get(), child_id.get(), index.get()),
            Mutation::Delete { node_id } => self.delete(node_id.get()),
        }
    }

    fn create(&mut self, node_id: u64, kind: ComponentKind) -> Result<(), HeadlessApplyError> {
        if self.nodes.contains_key(&node_id) {
            return Err(HeadlessApplyError::DuplicateNode);
        }
        if self.nodes.is_empty() {
            self.root = Some(node_id);
        }
        self.nodes.insert(node_id, HostNode::empty(kind));
        Ok(())
    }

    fn update_properties(
        &mut self,
        node_id: u64,
        set: &rmf_core::candidate::PropertySet,
        remove: &[PropertyId],
    ) -> Result<(), HeadlessApplyError> {
        let node = self
            .nodes
            .get_mut(&node_id)
            .ok_or(HeadlessApplyError::UnknownNode)?;
        if remove.iter().any(|id| !node.properties.contains_key(id)) {
            return Err(HeadlessApplyError::MissingProperty);
        }
        for id in remove {
            node.properties.remove(id);
        }
        for entry in set.entries() {
            node.properties.insert(entry.id(), entry.value().clone());
        }
        Ok(())
    }

    fn insert_child(
        &mut self,
        parent_id: u64,
        child_id: u64,
        index: u32,
    ) -> Result<(), HeadlessApplyError> {
        let index = usize::try_from(index).map_err(|_| HeadlessApplyError::InvalidChildRelation)?;
        let child = self
            .nodes
            .get(&child_id)
            .ok_or(HeadlessApplyError::UnknownNode)?;
        if child.parent.is_some()
            || self.root == Some(child_id)
            || self.has_ancestor(parent_id, child_id)
        {
            return Err(HeadlessApplyError::InvalidChildRelation);
        }
        let parent = self
            .nodes
            .get_mut(&parent_id)
            .ok_or(HeadlessApplyError::UnknownNode)?;
        if index > parent.children.len() {
            return Err(HeadlessApplyError::InvalidChildRelation);
        }
        parent.children.insert(index, child_id);
        if let Some(child) = self.nodes.get_mut(&child_id) {
            child.parent = Some(parent_id);
        }
        Ok(())
    }

    fn move_child(
        &mut self,
        parent_id: u64,
        child_id: u64,
        from: u32,
        to: u32,
    ) -> Result<(), HeadlessApplyError> {
        let from = usize::try_from(from).map_err(|_| HeadlessApplyError::InvalidChildRelation)?;
        let to = usize::try_from(to).map_err(|_| HeadlessApplyError::InvalidChildRelation)?;
        let parent = self
            .nodes
            .get_mut(&parent_id)
            .ok_or(HeadlessApplyError::UnknownNode)?;
        if parent.children.get(from) != Some(&child_id) || to >= parent.children.len() {
            return Err(HeadlessApplyError::InvalidChildRelation);
        }
        let moved = parent.children.remove(from);
        parent.children.insert(to, moved);
        Ok(())
    }

    fn remove_child(
        &mut self,
        parent_id: u64,
        child_id: u64,
        index: u32,
    ) -> Result<(), HeadlessApplyError> {
        let index = usize::try_from(index).map_err(|_| HeadlessApplyError::InvalidChildRelation)?;
        let parent = self
            .nodes
            .get_mut(&parent_id)
            .ok_or(HeadlessApplyError::UnknownNode)?;
        if parent.children.get(index) != Some(&child_id) {
            return Err(HeadlessApplyError::InvalidChildRelation);
        }
        parent.children.remove(index);
        let child = self
            .nodes
            .get_mut(&child_id)
            .ok_or(HeadlessApplyError::UnknownNode)?;
        if child.parent != Some(parent_id) {
            return Err(HeadlessApplyError::InvalidChildRelation);
        }
        child.parent = None;
        Ok(())
    }

    fn delete(&mut self, node_id: u64) -> Result<(), HeadlessApplyError> {
        let node = self
            .nodes
            .get(&node_id)
            .ok_or(HeadlessApplyError::UnknownNode)?;
        if self.root == Some(node_id) || node.parent.is_some() || !node.children.is_empty() {
            return Err(HeadlessApplyError::NodeNotDeletable);
        }
        self.nodes.remove(&node_id);
        Ok(())
    }

    fn has_ancestor(&self, mut node_id: u64, sought: u64) -> bool {
        loop {
            if node_id == sought {
                return true;
            }
            let Some(parent) = self.nodes.get(&node_id).and_then(|node| node.parent) else {
                return false;
            };
            node_id = parent;
        }
    }

    fn validate_graph(&self) -> Result<(), HeadlessApplyError> {
        let Some(root) = self.root else {
            return if self.nodes.is_empty() {
                Ok(())
            } else {
                Err(HeadlessApplyError::InvalidHostGraph)
            };
        };
        let mut visited = BTreeSet::new();
        let mut pending = vec![(root, None)];
        while let Some((node_id, expected_parent)) = pending.pop() {
            if !visited.insert(node_id) {
                return Err(HeadlessApplyError::InvalidHostGraph);
            }
            let node = self
                .nodes
                .get(&node_id)
                .ok_or(HeadlessApplyError::InvalidHostGraph)?;
            if node.parent != expected_parent {
                return Err(HeadlessApplyError::InvalidHostGraph);
            }
            pending.extend(
                node.children
                    .iter()
                    .rev()
                    .map(|child_id| (*child_id, Some(node_id))),
            );
        }
        if visited.len() == self.nodes.len() {
            Ok(())
        } else {
            Err(HeadlessApplyError::InvalidHostGraph)
        }
    }
}
