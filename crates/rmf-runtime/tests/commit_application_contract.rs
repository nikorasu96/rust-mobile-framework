//! Public contracts for apply-then-promote runtime orchestration.

use std::collections::VecDeque;
use std::error::Error;
use std::fmt::{self, Display, Formatter};

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, PropertySet, ValidatedTree,
};
use rmf_reconciliation::{MutationBatch, ReconcileLimits, Reconciler, SurfaceSnapshot};
use rmf_runtime::commit::{
    ApplyFailure, BatchApplier, CommitCoordinator, CommitError, CommitStatus, RecoveryError,
    SnapshotRemounter,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum HostError {
    Rejected,
    Partial,
    Remount,
}

impl Display for HostError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::Rejected => formatter.write_str("rejected"),
            Self::Partial => formatter.write_str("partial"),
            Self::Remount => formatter.write_str("remount"),
        }
    }
}

impl Error for HostError {}

#[derive(Debug, Default)]
struct RecordingApplier {
    outcomes: VecDeque<Result<(), ApplyFailure<HostError>>>,
    remount_outcomes: VecDeque<Result<(), HostError>>,
    calls: Vec<(u64, u64, usize)>,
    remount_calls: Vec<u64>,
}

impl RecordingApplier {
    fn with_outcome(outcome: Result<(), ApplyFailure<HostError>>) -> Self {
        Self {
            outcomes: VecDeque::from([outcome]),
            remount_outcomes: VecDeque::new(),
            calls: Vec::new(),
            remount_calls: Vec::new(),
        }
    }

    fn with_outcomes(
        outcomes: impl IntoIterator<Item = Result<(), ApplyFailure<HostError>>>,
        remount_outcomes: impl IntoIterator<Item = Result<(), HostError>>,
    ) -> Self {
        Self {
            outcomes: outcomes.into_iter().collect(),
            remount_outcomes: remount_outcomes.into_iter().collect(),
            calls: Vec::new(),
            remount_calls: Vec::new(),
        }
    }
}

impl SnapshotRemounter for RecordingApplier {
    type Error = HostError;

    fn remount_snapshot(&mut self, snapshot: &SurfaceSnapshot) -> Result<(), Self::Error> {
        self.remount_calls.push(snapshot.revision().get());
        self.remount_outcomes.pop_front().unwrap_or(Ok(()))
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

#[test]
fn successful_remount_unblocks_commits_at_the_confirmed_revision() {
    let applier = RecordingApplier::with_outcomes(
        [
            Err(ApplyFailure::FailedAfterMutation(HostError::Partial)),
            Ok(()),
        ],
        [Ok(())],
    );
    let mut coordinator = CommitCoordinator::new(applier);
    let failed = preparation(coordinator.confirmed_snapshot());
    assert_eq!(
        coordinator.apply(failed),
        Err(CommitError::FailedAfterMutation(HostError::Partial))
    );

    assert_eq!(coordinator.recover(), Ok(()));
    assert_eq!(
        coordinator.status(),
        CommitStatus::Ready {
            revision: SurfaceSnapshot::empty().revision()
        }
    );
    assert_eq!(coordinator.applier().remount_calls, [0]);

    let retry = preparation(coordinator.confirmed_snapshot());
    assert_eq!(coordinator.apply(retry), Ok(()));
    assert_eq!(coordinator.confirmed_snapshot().revision().get(), 1);
    assert_eq!(coordinator.applier().calls.len(), 2);
}

#[test]
fn failed_remount_remains_recovery_only_and_can_be_retried() {
    let applier = RecordingApplier::with_outcomes(
        [Err(ApplyFailure::FailedAfterMutation(HostError::Partial))],
        [Err(HostError::Remount), Ok(())],
    );
    let mut coordinator = CommitCoordinator::new(applier);
    let failed = preparation(coordinator.confirmed_snapshot());
    assert!(matches!(
        coordinator.apply(failed),
        Err(CommitError::FailedAfterMutation(HostError::Partial))
    ));
    let recovery_required = coordinator.status();

    assert_eq!(
        coordinator.recover(),
        Err(RecoveryError::RemountFailed(HostError::Remount))
    );
    assert_eq!(coordinator.status(), recovery_required);
    assert_eq!(coordinator.confirmed_snapshot().revision().get(), 0);

    assert_eq!(coordinator.recover(), Ok(()));
    assert_eq!(coordinator.applier().remount_calls, [0, 0]);
    assert_eq!(
        coordinator.status(),
        CommitStatus::Ready {
            revision: SurfaceSnapshot::empty().revision()
        }
    );
}

#[test]
fn recovery_is_rejected_without_host_call_when_not_required() {
    let mut coordinator = CommitCoordinator::new(RecordingApplier::default());

    assert_eq!(
        coordinator.recover(),
        Err(RecoveryError::NotRequired {
            revision: SurfaceSnapshot::empty().revision()
        })
    );
    assert!(coordinator.applier().remount_calls.is_empty());
}
