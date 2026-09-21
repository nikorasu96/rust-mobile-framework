# ADR-0011: Android host composition ordering

- Status: Accepted executable contract; Kotlin/JNI implementation remains compile-gated
- Date: 2026-09-21

## Context

ADRs 0005, 0008 and 0010 separately define generational native surfaces, the public facade
lifecycle and exclusive `ViewGroup` ownership. They do not determine the ordering between root
attachment, native creation, callback admission and cleanup. An adapter could satisfy each local
contract while briefly publishing a surface without a root, delivering a stale callback to the
facade, leaking a root after native failure, or removing resources owned by a replacement host.

Android requires UI hierarchy access on the main thread. Its JNI guidance recommends a small
boundary, limited marshalling and as little asynchronous cross-language coordination as practical.

## Decision

The Android adapter composes the existing contracts in this order:

1. claim the application-provided container;
2. attach the exact framework root synchronously on the main thread;
3. request native surface creation only after attachment succeeds;
4. accept callbacks only after the complete generational handle resolves, then apply facade
   sequence and close-state checks;
5. dispose the exact surface and release the exact root during terminal close.

If native creation fails, the attached root is released and no surface is published. If close
wins while creation is in flight, the root is released immediately; a later successful create is
disposed before the facade reaches `CLOSED`. Container, root or surface collisions fail the new
host while leaving foreign ownership intact. A generation outside Kotlin `Long`, although valid
inside the Rust `u64` registry, is disposed and fails closed before it can enter the facade.

The composition runs on the main thread after the facade's any-thread entry has marshalled work.
It does not add another JNI method or cross-language callback. Sub-contract failures are mapped to
closed typed outcomes; malformed calls reject atomically.

## Consequences

- `ACTIVE` implies both an attached owned root and an exact live surface handle.
- `CLOSED` and failed starts retain neither an owned mount nor the host's surface.
- A stale surface handle cannot advance facade callback sequence state.
- The composer orchestrates ports and owns no reconciliation, rendering or domain logic.
- This contract does not claim that Android views or JNI calls have executed.

## Verification

`contracts/android-host/v1` provides seven reviewed scenarios covering 21 actions and all nine
composition outcomes. Targeted regressions inject foreign container, root and surface ownership,
invalid identities and invalid transition order. The lifecycle model was extracted from fixture
I/O so both its original checks and the composer depend on one authoritative transition function.

Official references reviewed on 2026-09-21:

- Android processes and threads: <https://developer.android.com/guide/components/processes-and-threads>
- Android JNI tips: <https://developer.android.com/ndk/guides/jni-tips>
- Android `ViewGroup`: <https://developer.android.com/reference/android/view/ViewGroup>
