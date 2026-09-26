//! Public contracts for apply-then-promote runtime orchestration.

use std::collections::VecDeque;
use std::error::Error;
use std::fmt::{self, Display, Formatter};

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, PropertySet, ValidatedTree,
};
use rmf_reconciliation::{MutationBatch, ReconcileLimits, Reconciler, SurfaceSnapshot};
use rmf_runtime::commit::{
    ApplyFailure, BatchApplier, CommitCoordinator, CommitError, CommitStatus,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum HostError {
    Rejected,
    Partial,
}

impl Display for HostError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::Rejected => formatter.write_str("rejected"),
            Self::Partial => formatter.write_str("partial"),
        }
    }
}

impl Error for HostError {}

#[derive(Debug, Default)]
struct RecordingApplier {
    outcomes: VecDeque<Result<(), ApplyFailure<HostError>>>,
    calls: Vec<(u64, u64, usize)>,
}

impl RecordingApplier {
    fn with_outcome(outcome: Result<(), ApplyFailure<HostError>>) -> Self {
        Self {
            outcomes: VecDeque::from([outcome]),
            calls: Vec::new(),
        }
    }
}

impl BatchApplier for RecordingApplier {
    type Error = HostError;

    fn apply_batch(&mut self, batch: &MutationBatch) -> Result<(), ApplyFailure<Self::Error>> {
        self.calls.push((
            batch.base_revision().get(),
            batch.target_revision().get(),
            batch.operations().len(),
        ));
        self.outcomes.pop_front().unwrap_or(Ok(()))
    }
}

fn candidate() -> ValidatedTree {
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), vec![]);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid commit fixture: {error}"))
}

fn preparation(snapshot: &SurfaceSnapshot) -> rmf_reconciliation::PreparedCommit {
    let reconciler = Reconciler::new(
        ReconcileLimits::new(10)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    );
    reconciler
        .prepare(snapshot, &candidate())
        .unwrap_or_else(|error| unreachable!("fixture preparation succeeds: {error}"))
}

#[test]
fn promotes_snapshot_only_after_host_success() {
    let mut coordinator = CommitCoordinator::new(RecordingApplier::default());
    let prepared = preparation(coordinator.confirmed_snapshot());

    assert!(coordinator.apply(prepared).is_ok());
    assert_eq!(coordinator.confirmed_snapshot().revision().get(), 1);
    assert!(coordinator.confirmed_snapshot().root().is_some());
    assert_eq!(
        coordinator.status(),
        CommitStatus::Ready {
            revision: coordinator.confirmed_snapshot().revision()
        }
    );
    assert_eq!(coordinator.applier().calls, [(0, 1, 1)]);
}

#[test]
fn rejects_stale_batch_before_calling_host() {
    let mut coordinator = CommitCoordinator::new(RecordingApplier::default());
    let first = preparation(coordinator.confirmed_snapshot());
    let stale = preparation(&SurfaceSnapshot::empty());
    assert!(coordinator.apply(first).is_ok());

    assert_eq!(
        coordinator.apply(stale),
        Err(CommitError::StaleBatch {
            confirmed: coordinator.confirmed_snapshot().revision(),
            batch_base: SurfaceSnapshot::empty().revision(),
        })
    );
    assert_eq!(coordinator.applier().calls.len(), 1);
    assert_eq!(coordinator.confirmed_snapshot().revision().get(), 1);
}

#[test]
fn safe_rejection_keeps_confirmed_snapshot_ready() {
    let applier = RecordingApplier::with_outcome(Err(ApplyFailure::RejectedBeforeMutation(
        HostError::Rejected,
    )));
    let mut coordinator = CommitCoordinator::new(applier);
    let prepared = preparation(coordinator.confirmed_snapshot());

    assert_eq!(
        coordinator.apply(prepared),
        Err(CommitError::RejectedBeforeMutation(HostError::Rejected))
    );
    assert_eq!(coordinator.confirmed_snapshot().revision().get(), 0);
    assert_eq!(
        coordinator.status(),
        CommitStatus::Ready {
            revision: coordinator.confirmed_snapshot().revision()
        }
    );
    assert_eq!(coordinator.applier().calls.len(), 1);
}

#[test]
fn partial_failure_blocks_later_commits_without_calling_host() {
    let applier =
        RecordingApplier::with_outcome(Err(ApplyFailure::FailedAfterMutation(HostError::Partial)));
    let mut coordinator = CommitCoordinator::new(applier);
    let first = preparation(coordinator.confirmed_snapshot());

    assert_eq!(
        coordinator.apply(first),
        Err(CommitError::FailedAfterMutation(HostError::Partial))
    );
    let blocked = preparation(coordinator.confirmed_snapshot());
    assert_eq!(
        coordinator.apply(blocked),
        Err(CommitError::RecoveryRequired {
            confirmed: SurfaceSnapshot::empty().revision(),
            attempted: preparation(&SurfaceSnapshot::empty())
                .batch()
                .target_revision(),
        })
    );
    assert_eq!(coordinator.confirmed_snapshot().revision().get(), 0);
    assert_eq!(coordinator.applier().calls.len(), 1);
}
