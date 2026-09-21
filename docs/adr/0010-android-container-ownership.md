# ADR-0010: Android container ownership and detach semantics

- Status: Accepted contract; Kotlin implementation remains compile-gated
- Date: 2026-09-20

## Context

ADR-0009 gives `RmfSurfaceHost` an application-provided `ViewGroup`, but the public constructor
alone does not define exclusive ownership, partial attachment failure, cleanup or replacement
races. An adapter that calls `addView` and `removeView` without an explicit claim can mount two
hosts in one container, remove a replacement host's root from a stale callback, or leak a root
when close wins a queued attachment.

Android documents that `ViewGroup.addView` adds a child, `removeView` removes a specific view and
`View.getParent()` exposes whether a parent exists. These operations mutate the UI hierarchy and
therefore remain on the main thread under ADR-0008.

## Decision

### Exclusive claim

The internal adapter owns a registry keyed by container identity. A container has zero or one
current binding. `claim` fails atomically with `CONTAINER_ALREADY_OWNED` while any binding exists,
including a reservation whose root has not finished attaching.

Each successful claim allocates a positive monotonic mount ID within Kotlin `Long`. IDs never
wrap or repeat. The tuple `(container, host, mount)` identifies one binding; no partial identity
is accepted across asynchronous results.

### Attachment

A new binding begins `RESERVED` and emits `ADD_ROOT` on the main thread. Before calling Android,
the implementation must require that the framework-created root has no parent. Confirmation
moves the binding to `ATTACHED` and records that exact root. A root already attached or retired
from a prior host is rejected as `ROOT_NOT_DETACHED`.

An attachment failure releases the reservation. It does not leave a container claim that callers
cannot close or replace.

### Release and stale work

Release is idempotent:

- a current `RESERVED` binding is removed and its queued attachment is cancelled;
- a current `ATTACHED` binding is removed and emits `REMOVE_ROOT` for its exact root once;
- an unknown or obsolete tuple produces `DROP_STALE_RELEASE` without changing current state.

A successful attachment reported after its binding was released emits cleanup for that stale root
only. If the reported root is already the active root of another binding, it is dropped instead of
being removed. No stale result may replace, release or mutate the current binding.

The executable model retains retired test root identities to expose accidental reuse. This set is
an oracle technique, not a requirement for an unbounded production registry; the Kotlin adapter
will enforce ownership through host-local root references and Android parent checks.

## Consequences

- A caller must close the existing host before another host can claim the same container.
- A container becomes reusable immediately after cancellation, failure or exact-root removal.
- Cleanup never uses `removeAllViews`; application-owned siblings are outside framework ownership.
- Mount state stays in the Android adapter and does not enter the Rust domain or public API.
- The contract does not prove actual Android attachment, lifecycle integration or rendering.

## Verification

`contracts/android-container/v1` closes the vocabulary and contains eleven reviewed scenarios. The
dependency-free model verifies duplicate claims, close-before-attach, stale results, idempotent
release, safe replacement, root-parent exclusivity, main-thread enforcement and ID exhaustion.

The Android `ViewGroup` reference was reviewed on 2026-09-20 and was last updated 2026-08-28:
<https://developer.android.com/reference/android/view/ViewGroup>.

A bounded breadth-first explorer additionally checks 54 canonical actions from both the normal
initial registry and an allocator-exhaustion boundary state. It is exhaustive only for the two
containers, two hosts, three mount IDs, two root IDs and depth five declared by the explorer; it
is not an unbounded formal proof.
