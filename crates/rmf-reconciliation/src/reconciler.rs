use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::num::{NonZeroU32, NonZeroU64};

use rmf_core::candidate::{DeclarativeNode, ValidatedTree};

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
    /// Incremental reconciliation is not part of this initial-mount increment.
    IncrementalReconciliationUnavailable,
}

impl Display for ReconcileError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::RevisionExhausted => formatter.write_str("surface revision exhausted"),
            Self::IdentityExhausted => formatter.write_str("node identity allocator exhausted"),
            Self::ChildIndexOverflow => formatter.write_str("child index exceeds the v1 protocol"),
            Self::OperationLimitExceeded { limit } => {
                write!(formatter, "mutation batch exceeds the {limit}-operation limit")
            }
            Self::IncrementalReconciliationUnavailable => {
                formatter.write_str("incremental reconciliation is not implemented")
            }
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
        if current.root().is_some() {
            return Err(ReconcileError::IncrementalReconciliationUnavailable);
        }
        let target_revision = current
            .revision()
            .next()
            .ok_or(ReconcileError::RevisionExhausted)?;
        let mut builder = InitialMountBuilder::new(
            current
                .next_identity()
                .ok_or(ReconcileError::IdentityExhausted)?,
            self.limits.max_operations,
        );
        let root = builder.create_subtree(candidate.root())?;
        let batch = MutationBatch::new(
            current.revision(),
            target_revision,
            builder.operations,
        );
        let snapshot = SurfaceSnapshot::new(target_revision, root, builder.next_node_id);
        Ok(PreparedCommit::new(batch, snapshot))
    }
}

struct InitialMountBuilder {
    next_node_id: Option<NonZeroU64>,
    operation_limit: NonZeroU32,
    operations: Vec<Mutation>,
}

impl InitialMountBuilder {
    const fn new(next_node_id: NonZeroU64, operation_limit: NonZeroU32) -> Self {
        Self {
            next_node_id: Some(next_node_id),
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
            let index = ChildIndex::from_usize(position)
                .ok_or(ReconcileError::ChildIndexOverflow)?;
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

    fn allocate_identity(&mut self) -> Result<NodeId, ReconcileError> {
        let current = self
            .next_node_id
            .ok_or(ReconcileError::IdentityExhausted)?;
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
