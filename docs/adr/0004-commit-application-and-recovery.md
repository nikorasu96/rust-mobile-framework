# ADR-0004: Commit application and surface recovery

- Status: Accepted; apply-then-promote implemented in Rust; full-remount recovery pending
- Date: 2026-09-20
- Depends on: ADR-0002 and ADR-0003

## Context

Reconciliation prepares a next snapshot and an ordered mutation batch, but native UI toolkits
do not promise transactional rollback. The runtime needs an explicit rule for when logical
state is promoted and how it reacts when the host may be partially mutated. Without this rule,
an adapter could report a revision that the native hierarchy does not actually represent.

## Decision

### 1. Narrow outbound ports

The future runtime uses two capability-specific ports rather than a platform god interface:

```rust
pub trait BatchApplier {
    type Error: Error + Send + Sync + 'static;

    fn apply_batch(
        &mut self,
        batch: &MutationBatch,
    ) -> Result<(), ApplyFailure<Self::Error>>;
}

pub trait SnapshotRemounter {
    type Error: Error + Send + Sync + 'static;

    fn remount_snapshot(
        &mut self,
        snapshot: &SurfaceSnapshot,
    ) -> Result<(), Self::Error>;
}

pub enum ApplyFailure<E> {
    RejectedBeforeMutation(E),
    FailedAfterMutation(E),
}
```

An adapter returns `RejectedBeforeMutation` only when it can guarantee that no host view was
changed. Every ambiguous failure, timeout, lost callback or error after the first mutation is
`FailedAfterMutation`. Adapter prevalidation is internal to `apply_batch`; exposing a separate
validate call would introduce a time-of-check/time-of-use gap.

### 2. Surface states

Runtime owns an opaque state machine with these observable statuses:

| State | Meaning | Allowed next operation |
| --- | --- | --- |
| `Ready(revision)` | Host and committed snapshot agree | Begin batch at this revision |
| `Applying(base, target)` | Host call is in progress | Only its matching result |
| `Failed(base, attempted)` | Host may be partially changed | Begin full remount only |
| `Remounting(base)` | Confirmed snapshot is being restored | Only remount result |

`Applying` is set before calling the adapter. This rejects reentrant commits caused by native
callbacks. A surface state is serialized by its owning runtime executor; adapters never mutate
it directly.

### 3. Apply-then-promote protocol

1. Require `Ready` and a batch whose base equals the confirmed revision.
2. Retain the confirmed snapshot and set `Applying(base, target)`.
3. Call `BatchApplier::apply_batch` on the host UI thread.
4. On success, consume `PreparedCommit`, publish its snapshot and set `Ready(target)`.
5. On `RejectedBeforeMutation`, discard the preparation and return to `Ready(base)`.
6. On `FailedAfterMutation`, discard the preparation and enter `Failed(base, target)`.

The next snapshot is never observable before step 4. No rollback is claimed. A stale, busy or
recovery-required request is rejected before invoking the host.

### 4. Full-remount recovery

Recovery remounts the last confirmed snapshot, not the failed target. The runtime moves from
`Failed` to `Remounting`, calls `SnapshotRemounter` on the UI thread, and returns to
`Ready(base)` only after success. A remount failure returns to `Failed`; new commits remain
blocked. Repeated recovery is allowed and explicitly observable.

Surface disposal during apply or remount is a later lifecycle decision. It must not be added
implicitly to this contract.

### 5. Errors and observability

Runtime reports typed outcomes for stale batch, busy surface, recovery required, host rejection,
partial host failure and remount failure. Logs and traces include surface ID, base revision,
target revision, operation count, phase and stable adapter error code. Property values, text and
platform exception messages are excluded by default to avoid leaking application data.

Metrics count attempts, successful promotions, safe rejections, partial failures, remount
attempts and remount outcomes. A trace span begins before `Applying` and closes after the final
state transition.

### 6. Threading and panic policy

Preparation may occur off the UI thread; batch application, full remount and their state
transitions execute on the platform UI thread. Ports are synchronous in v1 to keep ownership and
reentrancy explicit. Android callbacks must be marshalled to that thread before calling them.

Expected failures use `Result`. Rust panics must not cross JNI. A future FFI adapter catches any
unexpected unwind at its outer boundary, records a sanitized fatal diagnostic and marks the
surface failed; this does not turn panics into ordinary domain errors.

## Executable contract

`contracts/commit-application/v1` specifies successful promotion, stale rejection, safe host
rejection, partial failure, busy protection, remount success, remount failure and retry. The
Python model is a dependency-free specification aid, not production runtime code.

## Consequences

- Logical revision and native hierarchy cannot silently diverge after a reported success.
- Safe rejection remains recoverable without unnecessary remount.
- Ambiguous host failure fails closed and blocks further mutation.
- Full remount has a single authoritative source: the last confirmed snapshot.
- Android must implement both small ports and accurate failure-phase classification.
- Asynchronous application, cancellation and surface disposal remain explicitly deferred.

## Implementation status

`rmf-runtime::commit` implements `BatchApplier`, explicit failure-phase classification,
revision-guarded application, success-only snapshot promotion, safe-rejection rollback to ready
and fail-closed blocking after a possibly partial mutation. `SnapshotRemounter` and the recovery
transition remain the next bounded increment; no compiled code currently claims host recovery.

## References

- [React Native render, commit and mount](https://reactnative.dev/architecture/render-pipeline)
- [Android threading on processes and threads](https://developer.android.com/guide/components/processes-and-threads)
- [Android JNI guidance](https://developer.android.com/ndk/guides/jni-tips)
