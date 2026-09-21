use std::num::NonZeroU64;
use std::sync::Arc;

use rmf_core::candidate::{ComponentKind, Key, PropertyId, PropertySet};

/// Runtime-owned positive identity that cannot be constructed by consumers.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct NodeId(NonZeroU64);

impl NodeId {
    pub(crate) const fn from_non_zero(value: NonZeroU64) -> Self {
        Self(value)
    }

    /// Returns the primitive identity for host adaptation and diagnostics.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0.get()
    }
}

/// Monotonic committed-tree revision.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct Revision(u64);

impl Revision {
    pub(crate) const fn initial() -> Self {
        Self(0)
    }

    pub(crate) fn next(self) -> Option<Self> {
        self.0.checked_add(1).map(Self)
    }

    /// Returns the primitive revision number.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0
    }
}

/// Checked child position in a mutation operation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ChildIndex(u32);

impl ChildIndex {
    pub(crate) fn from_usize(value: usize) -> Option<Self> {
        u32::try_from(value).ok().map(Self)
    }

    /// Returns the primitive child position.
    #[must_use]
    pub const fn get(self) -> u32 {
        self.0
    }
}

#[derive(Debug, Eq, PartialEq)]
struct CommittedNodeData {
    node_id: NodeId,
    kind: ComponentKind,
    key: Option<Key>,
    properties: PropertySet,
    children: Box<[CommittedNode]>,
}

/// Immutable committed node with parent-to-child shared ownership only.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CommittedNode(Arc<CommittedNodeData>);

impl CommittedNode {
    pub(crate) fn new(
        node_id: NodeId,
        kind: ComponentKind,
        key: Option<Key>,
        properties: PropertySet,
        children: Vec<Self>,
    ) -> Self {
        Self(Arc::new(CommittedNodeData {
            node_id,
            kind,
            key,
            properties,
            children: children.into_boxed_slice(),
        }))
    }

    /// Returns the runtime identity.
    #[must_use]
    pub fn node_id(&self) -> NodeId {
        self.0.node_id
    }

    /// Returns the component kind.
    #[must_use]
    pub fn kind(&self) -> ComponentKind {
        self.0.kind
    }

    /// Returns the optional sibling-scoped declaration key.
    #[must_use]
    pub fn key(&self) -> Option<&Key> {
        self.0.key.as_ref()
    }

    /// Returns the canonical committed properties.
    #[must_use]
    pub fn properties(&self) -> &PropertySet {
        &self.0.properties
    }

    /// Returns committed children in host order.
    #[must_use]
    pub fn children(&self) -> &[Self] {
        &self.0.children
    }
}

/// Immutable host mutation vocabulary.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Mutation {
    /// Allocate a host representation.
    Create {
        /// Runtime identity allocated by reconciliation.
        node_id: NodeId,
        /// Host component kind.
        kind: ComponentKind,
    },
    /// Apply a canonical property delta.
    UpdateProperties {
        /// Target runtime identity.
        node_id: NodeId,
        /// Properties to set.
        set: PropertySet,
        /// Property identities to remove.
        remove: Box<[PropertyId]>,
    },
    /// Attach a child at a checked index.
    InsertChild {
        /// Parent runtime identity.
        parent_id: NodeId,
        /// Child runtime identity.
        child_id: NodeId,
        /// Destination position.
        index: ChildIndex,
    },
    /// Reorder a child under the same parent.
    MoveChild {
        /// Parent runtime identity.
        parent_id: NodeId,
        /// Child runtime identity.
        child_id: NodeId,
        /// Current position.
        from: ChildIndex,
        /// Destination position.
        to: ChildIndex,
    },
    /// Detach a child from its parent.
    RemoveChild {
        /// Parent runtime identity.
        parent_id: NodeId,
        /// Child runtime identity.
        child_id: NodeId,
        /// Current position.
        index: ChildIndex,
    },
    /// Release a detached host representation.
    Delete {
        /// Runtime identity to release.
        node_id: NodeId,
    },
}

/// Immutable, revision-bound host mutation sequence.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MutationBatch {
    base_revision: Revision,
    target_revision: Revision,
    operations: Box<[Mutation]>,
}

impl MutationBatch {
    pub(crate) fn new(
        base_revision: Revision,
        target_revision: Revision,
        operations: Vec<Mutation>,
    ) -> Self {
        Self {
            base_revision,
            target_revision,
            operations: operations.into_boxed_slice(),
        }
    }

    /// Returns the revision required before application.
    #[must_use]
    pub const fn base_revision(&self) -> Revision {
        self.base_revision
    }

    /// Returns the revision produced after successful application.
    #[must_use]
    pub const fn target_revision(&self) -> Revision {
        self.target_revision
    }

    /// Returns operations in deterministic application order.
    #[must_use]
    pub fn operations(&self) -> &[Mutation] {
        &self.operations
    }
}

/// Immutable committed surface state and its private identity allocator.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SurfaceSnapshot {
    revision: Revision,
    root: Option<CommittedNode>,
    next_node_id: Option<NonZeroU64>,
}

impl SurfaceSnapshot {
    /// Creates the only valid public initial state.
    #[must_use]
    pub fn empty() -> Self {
        Self {
            revision: Revision::initial(),
            root: None,
            next_node_id: NonZeroU64::new(1),
        }
    }

    pub(crate) const fn new(
        revision: Revision,
        root: CommittedNode,
        next_node_id: Option<NonZeroU64>,
    ) -> Self {
        Self {
            revision,
            root: Some(root),
            next_node_id,
        }
    }

    pub(crate) const fn next_identity(&self) -> Option<NonZeroU64> {
        self.next_node_id
    }

    /// Returns the committed revision.
    #[must_use]
    pub const fn revision(&self) -> Revision {
        self.revision
    }

    /// Returns the optional committed root.
    #[must_use]
    pub const fn root(&self) -> Option<&CommittedNode> {
        self.root.as_ref()
    }
}

impl Default for SurfaceSnapshot {
    fn default() -> Self {
        Self::empty()
    }
}

/// Atomic preparation containing both host work and the unpublished next snapshot.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PreparedCommit {
    batch: MutationBatch,
    snapshot: SurfaceSnapshot,
}

impl PreparedCommit {
    pub(crate) const fn new(batch: MutationBatch, snapshot: SurfaceSnapshot) -> Self {
        Self { batch, snapshot }
    }

    /// Borrows the batch for host application.
    #[must_use]
    pub const fn batch(&self) -> &MutationBatch {
        &self.batch
    }

    /// Consumes the preparation after confirmed host success.
    #[must_use]
    pub fn into_snapshot(self) -> SurfaceSnapshot {
        self.snapshot
    }
}
