# Architecture

## Direction of dependencies

```text
rmf-core <- rmf-reconciliation <- rmf-runtime <- platform/render adapters <- composition roots
```

`rmf-core` owns declarative values and validation. Its `candidate` module removes
caller-assigned runtime identities and enforces the closed v1 property schema and defensive
tree limits. `rmf-reconciliation` owns runtime identities, immutable snapshots and pure mutation
calculation. It implements deterministic initial mounts, property updates, and one linear-time keyed
child move, insertion, removal or replacement per sibling list. Multiple structural changes and
multi-move reorders remain unavailable through an explicit typed error. `rmf-runtime` owns application
orchestration and outbound ports. Its `CommitCoordinator` checks the confirmed base revision,
applies an immutable batch and publishes the prepared snapshot only after adapter success. Safe
host rejection remains ready; a possibly partial mutation blocks later commits until the adapter
successfully remounts the last confirmed snapshot. Failed remounts remain retryable without
promoting the failed candidate.
Adapters implement those ports. Composition roots select
concrete adapters and are the only place allowed to wire them.

`HeadlessMutationAdapter` is the first compiled adapter for both runtime ports. It evaluates a
complete batch against a private in-memory host copy, validates reachability and ownership, and
publishes only a valid result. Because no observable mutation precedes validation, adapter errors
are safe pre-mutation rejections. Remount reconstructs the exact confirmed snapshot.

## Boundary rules

1. Core crates cannot depend on Android, Kotlin, JNI, TypeScript, renderers, or CLI code.
2. Reconciliation may depend only on `rmf-core`; core cannot depend on reconciliation.
3. Runtime crates can depend on both inward crates, but not on concrete adapters.
4. Adapters can depend inward and cannot expose platform handles through core types.
5. FFI is isolated inside platform adapters and presents a safe Rust boundary inward.
6. Public packages do not access crate internals; versioned facade APIs mediate access.
7. Dependency cycles are defects and block an increment.

`scripts/check_architecture.py` enforces the current layer order. New workspace
locations must be classified deliberately; unclassified packages fail the check.
The domain core and planned reconciliation service forbid every external Cargo dependency
to keep their semantics auditable while the foundational model is still small.

## Target repository topology

```text
crates/       # platform-independent domain, ports, runtime and public Rust facade
adapters/     # renderer, storage, networking and tooling adapters
platforms/    # Android first; iOS after Android compatibility gates
packages/     # public TypeScript API and CLI packages
examples/     # executable composition roots
tests/        # cross-package contract and end-to-end suites
benchmarks/   # executable composition roots for repeatable performance gates
docs/         # ADRs, roadmap, compatibility and operational documentation
```

Empty target directories are introduced only when their first real artifact exists.

## Runtime flow

1. A frontend produces a declarative description.
2. The core validates component, property and structural invariants.
3. Reconciliation assigns identities and prepares a committed snapshot plus mutation batch.
4. Runtime applies the batch through a narrow port and promotes the snapshot on success.
5. A platform adapter maps commands to native views or a renderer.
6. Platform events return through typed inbound commands, never raw platform objects.

ADR-0004 defines the runtime's apply-then-promote state machine. A safe host rejection keeps
the confirmed revision; a possibly partial failure blocks new commits until the adapter fully
remounts the last confirmed snapshot.

ADR-0005 assigns surface creation, disposal and callback routing to the runtime lifecycle
registry. Cross-boundary work carries a positive `(surface_id, generation)` value; the complete
pair is resolved before domain or commit logic runs. Generations are monotonic and never reused,
so a callback queued for a destroyed surface cannot target its replacement.

ADR-0006 fixes the Android JNI v1 boundary as one registered entry point using signed fixed-width
primitives and copied byte arrays. Its admission layer rejects unknown ABI versions, operations,
threads, invalid handles and oversized payloads before runtime access. A fixed versioned response
frame carries typed outcomes; Rust pointers, borrows and Android object identity never cross.
Event and commit-result bytes carry a second operation-bound header; both layers validate magic,
version, reserved bytes and exact lengths before any operation body or runtime state is touched.
The safe body layer then maps only a positive node plus registered click event, or consecutive
commit revisions plus an ADR-0004 outcome/reason pair. Unknown discriminants and inconsistent
classifications fail before orchestration; no platform object or free-form error crosses inward.
The boundary is additionally exercised by exhaustive one-bit mutation over canonical messages.
Accepted mutations must be canonical on re-encoding, preventing permissive alternate encodings;
rejections remain confined to the versioned error registry.

ADR-0007 fixes Android packaging as three roles: an internal Rust `cdylib`, one publishable Kotlin
AAR and one sample composition root. Cargo owns native compilation; Gradle only stages generated
`.so` outputs into the AAR. The JNI crate depends inward on runtime, the Kotlin facade sees only
the versioned byte contract, and domain crates remain unaware of Android. A machine-readable
topology check rejects cycles, extra native exports, toolchain drift and expanded publication.

ADR-0008 fixes the public Kotlin surface facade lifecycle before implementation. Any-thread
create and close requests marshal to the Android main queue, while native results and callbacks
must already arrive on that thread. The facade owns one complete generational handle, suppresses
callbacks as soon as close is requested, makes close idempotent and disposes a handle returned by
a create/close race without ever publishing it as active. These policies remain in the Android
adapter and do not leak scheduling or lifecycle state into the domain.
The facade model and its transition invariants are separate modules: reviewed scenarios and
bounded exhaustive exploration reuse the same state validator without coupling it to fixture I/O.

ADR-0009 limits the published Android API to one final `RmfSurfaceHost` class with a public
`ViewGroup` constructor and idempotent `close()`. JNI bytes, native handles, bridge objects and
runtime types stay internal. A closed manifest cross-checks the API against Android module
ownership; strict explicit API mode and compiled ABI validation become mandatory when Kotlin
source can pass the build gates.

ADR-0010 defines the internal container adapter below that public type. One `ViewGroup` can have
only one current host claim, and each claim receives a positive monotonic mount ID. Attachment and
exact-root removal are main-thread effects. Releasing a reservation cancels it, releasing an
attached claim removes only its owned root, and stale results cannot alter a newer claim on the
same container. Root identities are test-model values, not public Android IDs or native handles.
Reviewed scenarios and bounded exhaustive exploration share a separate invariant module, keeping
state validation independent from fixture parsing and search orchestration.

ADR-0011 composes facade, container and surface lifecycles without moving their rules into a god
adapter. The main-thread composer claims and attaches the exact root before requesting native
creation, validates complete generational handles before facade callbacks, and disposes/releases
only the current host's resources. An active facade therefore always has both an attached root and
a live surface; failed or closed hosts retain neither. The surface transition model is separated
from fixture I/O so every contract consumes one authoritative implementation.

The executable headless composition root now uses validated declarations, reconciliation,
`CommitCoordinator` and `HeadlessMutationAdapter`; callers no longer assign its node identities.
The bootstrap `Renderer` path still renders a complete caller-identified tree only for legacy
renderer/runtime contract coverage. The benchmark and example use the committed pipeline. New
platform work uses the commit ports; Android adapters do not
calculate tree identity or diff semantics. Replacing that remaining coverage and removing the
bootstrap path remain explicit gates before Android integration.
