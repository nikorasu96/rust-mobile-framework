# ADR-0005: Surface lifecycle and generational handles

- Status: Accepted; runtime registry implemented in Rust
- Date: 2026-09-20
- Depends on: ADR-0003 and ADR-0004

## Context

Android work can outlive an Activity, View hierarchy or framework surface. Queued events and
host results may arrive after disposal, while an application may later create a new surface with
the same public identifier. Routing by that identifier alone would let a stale callback mutate
or acknowledge the replacement surface.

## Decision

### 1. Handle identity

Every active surface is addressed by `SurfaceHandle { surface_id, generation }`. Both fields are
positive `u64` values. `surface_id` is the caller-selected logical slot; `generation` is assigned
by the runtime from one process-wide monotonic allocator. A handle is valid only while its exact
pair is active.

Generations are never reused during the runtime process. The allocator has explicit `Available`
and `Exhausted` states so overflow cannot wrap, panic or silently reuse zero. Exhaustion rejects
creation without modifying registry state.

### 2. Registry ownership and operations

The future runtime owns a registry behind its serialized executor. Its narrow operations are:

- `create(surface_id) -> Result<SurfaceHandle, CreateSurfaceError>`;
- `dispose(handle) -> Result<(), HandleError>`;
- `resolve(handle) -> Result<SurfaceAccess, HandleError>` for inbound callbacks.

Creating an already-active logical slot is rejected. Disposal removes the exact handle before
platform cleanup begins. Repeated or stale disposal is rejected and cannot affect a replacement.
All platform callbacks, including events and host completion signals, resolve the complete handle
before reaching commit or domain logic.

### 3. Interaction with commit application

Lifecycle commands and commit transitions are serialized on the surface-owning runtime executor.
ADR-0004 ports remain synchronous, so disposal does not interrupt a call already executing on the
UI thread. Once that call returns, queued disposal invalidates the handle before later callbacks
are processed. A callback carrying the prior generation is then rejected as `STALE_SURFACE_HANDLE`.

This contract does not claim cancellation of native work. Platform cleanup is idempotent and best
effort after logical invalidation; cleanup diagnostics cannot reactivate the surface.

### 4. FFI and threading boundary

Kotlin stores the two numeric handle fields, never a Rust pointer or borrowed reference. JNI
converts them into validated value types and marshals lifecycle operations to the owning executor.
No Java/Kotlin object identity participates in domain identity. Handles are transport values, not
a stable public ABI, and callbacks containing zero, malformed or unknown fields fail closed.

### 5. Observability and privacy

Structured diagnostics include operation, surface ID, generation and stable outcome code. They do
not include component properties, text or platform exception messages by default. Metrics count
creation, duplicate rejection, disposal, stale callback rejection and allocator exhaustion.

## Executable contract

`contracts/surface-lifecycle/v1` covers creation, exact callback routing, disposal, logical-slot
reuse, stale callback/disposal rejection, isolation between surfaces and allocator exhaustion.
The dependency-free Python model remains an independent executable specification. Production
identity allocation, creation, disposal and callback admission are implemented in
`rmf-runtime::surface` and verified with the pinned Rust toolchain in CI.

## Consequences

- Late callbacks cannot target a recreated surface with the same logical ID.
- No raw native or Rust pointer becomes a cross-language lifetime token.
- Disposal is logically atomic even when native cleanup reports a later failure.
- A process-wide monotonic generation allocator has a finite, explicit exhaustion outcome.
- Cancellation and Android host cleanup implementation remain future adapter responsibilities.

## References

- [Android lifecycle-aware cleanup](https://developer.android.com/topic/libraries/architecture/lifecycle)
- [Android JNI guidance](https://developer.android.com/ndk/guides/jni-tips)
- [Rust `NonZeroU64`](https://doc.rust-lang.org/std/num/type.NonZeroU64.html)
