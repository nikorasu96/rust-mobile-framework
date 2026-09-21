# ADR-0008: Android Kotlin surface facade lifecycle

- Status: Accepted
- Date: 2026-09-20
- Owners: Android framework adapter maintainers

## Context

ADR-0007 assigns the public Android API, native view host and main-thread marshalling to one AAR.
The API must tolerate calls from arbitrary application threads without allowing native UI work,
late callbacks or a create/close race to corrupt a surface. A Kotlin implementation cannot yet be
compiled in the available environment, so its observable lifecycle must be fixed independently.

## Decision

The public unit will be `dev.rmf.android.RmfSurfaceHost`. One instance owns at most one complete
`(surface_id, generation)` handle and exposes creation and idempotent close requests. Public
requests may originate on any thread; worker requests enqueue one main-thread action. Native
results and callbacks are accepted only on the main thread.

The closed state machine is `NEW`, `CREATE_QUEUED`, `CREATING`, `ACTIVE`, `CLOSE_QUEUED`,
`CLOSE_PENDING_CREATE`, `CLOSING`, `CLOSED`, and `FAILED`. Terminal states never reactivate.
Closing before queued creation cancels it. Closing while native creation is outstanding waits for
the result and immediately disposes any returned handle without making the facade active.

The first close request suppresses callbacks immediately, including while the close task waits in
the main queue. Repeated close requests neither enqueue additional work nor invoke native disposal
again. A callback is delivered only when the facade is active, its complete handle matches, and
its positive sequence is greater than every sequence already delivered.

Identifiers use the positive Kotlin `Long` range. Native failure becomes the stable terminal
`FAILED` state with a typed phase and reason. Disposal failure clears the handle because the
facade may not safely route further work to an uncertain native resource.

`contracts/android-facade/v1` is the executable authority. Kotlin code must pass these same
scenarios as contract tests before it can be accepted.

## Boundaries

- The facade contains lifecycle orchestration, not reconciliation, layout or domain behavior.
- The Android main queue is an outbound scheduling detail; it is not exposed to the Rust domain.
- Native callbacks carry values from ADR-0006, never Android objects or native pointers.
- No automatic retry is performed after failure; recovery creates a new facade and therefore a
  new generational surface handle.

## Consequences

The API has deterministic race behavior and a small testable state surface before Android source
exists. Queued close requires one small origin marker so the main-thread action can distinguish
cancel-before-create, close-during-create and active disposal. This contract does not prove
Android queue ordering, JNI attachment, process recreation or actual lifecycle-owner integration;
those require compiled Kotlin and device tests.

