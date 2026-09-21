//! Pure deterministic reconciliation from validated declarations to immutable commits.

mod reconciler;
mod types;

pub use reconciler::{InvalidReconcileLimits, ReconcileError, ReconcileLimits, Reconciler};
pub use types::{
    ChildIndex, CommittedNode, Mutation, MutationBatch, NodeId, PreparedCommit, Revision,
    SurfaceSnapshot,
};
