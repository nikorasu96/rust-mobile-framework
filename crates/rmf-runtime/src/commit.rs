//! Apply-then-promote orchestration for one committed surface.

use std::error::Error;
use std::fmt::{self, Display, Formatter};

use rmf_reconciliation::{MutationBatch, PreparedCommit, Revision, SurfaceSnapshot};

/// Failure phase reported by a host mutation adapter.
#[derive(Debug, Eq, PartialEq)]
pub enum ApplyFailure<E> {
    /// The adapter guarantees that no host mutation occurred.
    RejectedBeforeMutation(E),
    /// The host may be partially mutated and requires recovery.
    FailedAfterMutation(E),
}

impl<E> Display for ApplyFailure<E>
where
    E: Display,
{
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::RejectedBeforeMutation(error) => {
                write!(formatter, "host rejected batch before mutation: {error}")
            }
            Self::FailedAfterMutation(error) => {
                write!(formatter, "host failed after mutation began: {error}")
            }
        }
    }
}

impl<E> Error for ApplyFailure<E> where E: Error + 'static {}

/// Capability-specific outbound port for applying one immutable mutation batch.
pub trait BatchApplier {
    /// Adapter-specific error classified by mutation phase.
    type Error: Error + Send + Sync + 'static;

    /// Applies the complete batch in its deterministic order.
    ///
    /// `RejectedBeforeMutation` is valid only when no host state changed. Any ambiguous or
    /// partial failure must be reported as `FailedAfterMutation`.
    ///
    /// # Errors
    ///
    /// Returns the adapter's failure with an explicit mutation phase.
    fn apply_batch(&mut self, batch: &MutationBatch) -> Result<(), ApplyFailure<Self::Error>>;
}

/// Capability-specific outbound port for restoring one complete confirmed snapshot.
pub trait SnapshotRemounter {
    /// Adapter-specific remount error.
    type Error: Error + Send + Sync + 'static;

    /// Replaces the host tree with exactly the supplied confirmed snapshot.
    ///
    /// Implementations must treat every call as a complete retry. The runtime may invoke this
    /// method again after an error because host state remains unknown until a remount succeeds.
    ///
    /// # Errors
    ///
    /// Returns the adapter error when the host cannot confirm the complete snapshot.
    fn remount_snapshot(&mut self, snapshot: &SurfaceSnapshot) -> Result<(), Self::Error>;
}

/// Observable state of commit application for one surface.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CommitStatus {
    /// The host agrees with the confirmed snapshot.
    Ready {
        /// Confirmed revision.
        revision: Revision,
    },
    /// A matching batch is currently being applied.
    Applying {
        /// Confirmed base revision.
        base: Revision,
        /// Candidate target revision.
        target: Revision,
    },
    /// The last confirmed snapshot is currently being remounted.
    Remounting {
        /// Revision being restored.
        confirmed: Revision,
        /// Revision whose application caused recovery.
        attempted: Revision,
    },
    /// Host state may be partial; further commits are blocked pending remount recovery.
    RecoveryRequired {
        /// Last confirmed revision.
        confirmed: Revision,
        /// Revision whose application failed.
        attempted: Revision,
    },
}

/// Typed full-remount recovery failure.
#[derive(Debug, Eq, PartialEq)]
pub enum RecoveryError<E> {
    /// The host already agrees with the confirmed revision.
    NotRequired {
        /// Confirmed revision.
        revision: Revision,
    },
    /// A commit application is still in progress.
    BusyApplying {
        /// Confirmed base revision.
        base: Revision,
        /// Candidate target revision.
        target: Revision,
    },
    /// A remount call is still in progress.
    BusyRemounting {
        /// Revision being restored.
        confirmed: Revision,
        /// Revision whose application caused recovery.
        attempted: Revision,
    },
    /// The host did not confirm a complete remount; recovery may be retried.
    RemountFailed(E),
}

impl<E> Display for RecoveryError<E>
where
    E: Display,
{
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotRequired { revision } => write!(
                formatter,
                "surface at revision {} does not require recovery",
                revision.get()
            ),
            Self::BusyApplying { base, target } => write!(
                formatter,
                "surface is applying revision {} from base {}",
                target.get(),
                base.get()
            ),
            Self::BusyRemounting {
                confirmed,
                attempted,
            } => write!(
                formatter,
                "surface is remounting revision {} after attempting {}",
                confirmed.get(),
                attempted.get()
            ),
            Self::RemountFailed(error) => write!(formatter, "host remount failed: {error}"),
        }
    }
}

impl<E> Error for RecoveryError<E> where E: Error + 'static {}

/// Typed commit-application failure without exposing candidate data.
#[derive(Debug, Eq, PartialEq)]
pub enum CommitError<E> {
    /// A previous host call has not reached a classified result.
    Busy {
        /// Confirmed base revision of the in-flight batch.
        base: Revision,
        /// Target revision of the in-flight batch.
        target: Revision,
    },
    /// The prepared batch does not start at the confirmed revision.
    StaleBatch {
        /// Runtime's confirmed revision.
        confirmed: Revision,
        /// Revision required by the batch.
        batch_base: Revision,
    },
    /// A prior partial host failure blocks new mutations until recovery.
    RecoveryRequired {
        /// Runtime's last confirmed revision.
        confirmed: Revision,
        /// Revision whose application may be partial.
        attempted: Revision,
    },
    /// The host safely rejected the batch without mutation.
    RejectedBeforeMutation(E),
    /// The host may be partially mutated and is now recovery-only.
    FailedAfterMutation(E),
}

impl<E> Display for CommitError<E>
where
    E: Display,
{
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::Busy { base, target } => write!(
                formatter,
                "surface is applying revision {} from base {}",
                target.get(),
                base.get()
            ),
            Self::StaleBatch {
                confirmed,
                batch_base,
            } => write!(
                formatter,
                "stale mutation batch: confirmed revision {}, batch base {}",
                confirmed.get(),
                batch_base.get()
            ),
            Self::RecoveryRequired {
                confirmed,
                attempted,
            } => write!(
                formatter,
                "surface requires recovery at revision {} after attempting {}",
                confirmed.get(),
                attempted.get()
            ),
            Self::RejectedBeforeMutation(error) => {
                write!(formatter, "host rejected batch before mutation: {error}")
            }
            Self::FailedAfterMutation(error) => {
                write!(formatter, "host failed after mutation began: {error}")
            }
        }
    }
}

impl<E> Error for CommitError<E> where E: Error + 'static {}

/// Serial commit coordinator that owns the last confirmed snapshot.
#[derive(Debug)]
pub struct CommitCoordinator<A> {
    applier: A,
    confirmed: SurfaceSnapshot,
    status: CommitStatus,
}

impl<A> CommitCoordinator<A>
where
    A: BatchApplier,
{
    /// Creates a coordinator at the empty initial revision.
    #[must_use]
    pub fn new(applier: A) -> Self {
        let confirmed = SurfaceSnapshot::empty();
        let status = CommitStatus::Ready {
            revision: confirmed.revision(),
        };
        Self {
            applier,
            confirmed,
            status,
        }
    }

    /// Applies a prepared batch and publishes its snapshot only after host success.
    ///
    /// # Errors
    ///
    /// Rejects stale batches before calling the adapter. A safe host rejection retains the
    /// confirmed snapshot and remains ready. A possibly partial host failure blocks later commits.
    pub fn apply(&mut self, prepared: PreparedCommit) -> Result<(), CommitError<A::Error>> {
        let confirmed_revision = self.confirmed.revision();
        match self.status {
            CommitStatus::Ready { .. } => {}
            CommitStatus::Applying { base, target } => {
                return Err(CommitError::Busy { base, target });
            }
            CommitStatus::Remounting {
                confirmed,
                attempted,
            } => {
                return Err(CommitError::Busy {
                    base: confirmed,
                    target: attempted,
                });
            }
            CommitStatus::RecoveryRequired {
                confirmed,
                attempted,
            } => {
                return Err(CommitError::RecoveryRequired {
                    confirmed,
                    attempted,
                });
            }
        }

        let base = prepared.batch().base_revision();
        let target = prepared.batch().target_revision();
        if base != confirmed_revision {
            return Err(CommitError::StaleBatch {
                confirmed: confirmed_revision,
                batch_base: base,
            });
        }

        self.status = CommitStatus::Applying { base, target };
        match self.applier.apply_batch(prepared.batch()) {
            Ok(()) => {
                self.confirmed = prepared.into_snapshot();
                self.status = CommitStatus::Ready { revision: target };
                Ok(())
            }
            Err(ApplyFailure::RejectedBeforeMutation(error)) => {
                self.status = CommitStatus::Ready {
                    revision: confirmed_revision,
                };
                Err(CommitError::RejectedBeforeMutation(error))
            }
            Err(ApplyFailure::FailedAfterMutation(error)) => {
                self.status = CommitStatus::RecoveryRequired {
                    confirmed: confirmed_revision,
                    attempted: target,
                };
                Err(CommitError::FailedAfterMutation(error))
            }
        }
    }

    /// Returns the last snapshot confirmed by the host.
    #[must_use]
    pub const fn confirmed_snapshot(&self) -> &SurfaceSnapshot {
        &self.confirmed
    }

    /// Returns the current sanitized application state.
    #[must_use]
    pub const fn status(&self) -> CommitStatus {
        self.status
    }

    /// Returns shared adapter access for diagnostics and composition roots.
    #[must_use]
    pub const fn applier(&self) -> &A {
        &self.applier
    }

    /// Consumes the coordinator and returns the adapter.
    #[must_use]
    pub fn into_applier(self) -> A {
        self.applier
    }
}

impl<A> CommitCoordinator<A>
where
    A: BatchApplier + SnapshotRemounter,
{
    /// Restores the last confirmed snapshot after a possibly partial host mutation.
    ///
    /// A failed remount leaves the coordinator recovery-only and can be retried. Only a complete
    /// host success returns the coordinator to `Ready` and permits later commits.
    ///
    /// # Errors
    ///
    /// Rejects recovery when it is unnecessary or another host call is active. Returns the
    /// adapter error without changing the confirmed snapshot when a remount fails.
    pub fn recover(&mut self) -> Result<(), RecoveryError<<A as SnapshotRemounter>::Error>> {
        let (confirmed, attempted) = match self.status {
            CommitStatus::Ready { revision } => {
                return Err(RecoveryError::NotRequired { revision });
            }
            CommitStatus::Applying { base, target } => {
                return Err(RecoveryError::BusyApplying { base, target });
            }
            CommitStatus::Remounting {
                confirmed,
                attempted,
            } => {
                return Err(RecoveryError::BusyRemounting {
                    confirmed,
                    attempted,
                });
            }
            CommitStatus::RecoveryRequired {
                confirmed,
                attempted,
            } => (confirmed, attempted),
        };

        self.status = CommitStatus::Remounting {
            confirmed,
            attempted,
        };
        match self.applier.remount_snapshot(&self.confirmed) {
            Ok(()) => {
                self.status = CommitStatus::Ready {
                    revision: confirmed,
                };
                Ok(())
            }
            Err(error) => {
                self.status = CommitStatus::RecoveryRequired {
                    confirmed,
                    attempted,
                };
                Err(RecoveryError::RemountFailed(error))
            }
        }
    }
}
