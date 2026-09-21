# ADR-0006: Android JNI boundary v1

- Status: Accepted contract; implementation blocked by TD-001 and TD-005
- Date: 2026-09-20
- Depends on: ADR-0004 and ADR-0005

## Context

The Android adapter must transport lifecycle and host events without exposing Rust pointers,
borrows, platform objects or internal domain representations. JNI also has thread-local
environment state, local-reference lifetimes and a pending-exception state that make a broad or
object-heavy interface difficult to audit.

## Decision

### 1. One registered entry point

The first Android adapter exposes one statically registered Kotlin method:

```text
NativeBridge.nativeDispatch(
    abiVersion: Int,
    operation: Int,
    requestId: Long,
    surfaceId: Long,
    generation: Long,
    payload: ByteArray,
): ByteArray
```

Its JVM descriptor is `(IIJJJ[B)[B`. `JNI_OnLoad` registers the method with
`RegisterNatives`; only `JNI_OnLoad` is exported. The v1 operation codes are create surface,
dispose surface, dispatch event and report commit result. The manifest in
`contracts/android-ffi/v1/contract.json` is the machine-readable authority.

### 2. ABI-safe values and versioning

Only JNI fixed-width primitives and owned byte arrays cross the boundary. No Rust struct, enum,
reference, trait object, allocator-owned pointer, `JNIEnv`, `jobject` identity or native address is
transported as framework state.

Kotlin `Long` is signed, so transport identifiers are restricted to `1..=i64::MAX`; Rust converts
them to its positive internal types only after validation. A zero generation is permitted solely
for create requests, where no handle exists yet. Every other operation carries the complete
positive `(surface_id, generation)` pair from ADR-0005.

ABI major version `1` is mandatory. Unknown versions and operation codes fail closed. A future
incompatible signature or meaning requires a new major version and parallel migration; fields are
not silently reinterpreted.

### 3. Payload and ownership

Payloads are copied from `jbyteArray` with region APIs into Rust-owned bytes before entering the
safe adapter. The maximum v1 payload is 1 MiB. Create and dispose require an empty payload;
event and commit-result payloads use a fixed 16-byte `RMP1` little-endian header containing schema
version, operation, body length and four reserved zero bytes. The declared operation must match
the JNI argument before operation-specific safe code receives the body.

The v1 event body is exactly 24 bytes: positive `node_id`, registered `event_code`, zero flags,
positive per-surface sequence and zero reserved bytes. V1 registers only `CLICK`; adding an event
requires a reviewed numeric code and compatible decoder update. The commit-result body is also
exactly 24 bytes: consecutive base/target revisions, outcome, reason and zero flags. Accepted
pairs are `APPLIED/NONE`, `REJECTED_BEFORE_MUTATION/HOST_VALIDATION`, and
`FAILED_AFTER_MUTATION` with `HOST_UNAVAILABLE` or `HOST_INTERNAL`. Free-form host text, Android
objects and component data do not cross this body contract.
The native call retains no local reference or borrowed array pointer after return. The returned
array is owned by ART. V1 stores no global JNI references.

### 4. Threading

The Kotlin facade asserts and marshals every call to the Android main thread. Native code verifies
that policy before routing the owned request to the serialized runtime executor. A call observed
off the main thread returns `WRONG_THREAD` without touching lifecycle, commit or domain state.
`JNIEnv` is never cached or shared between threads.

### 5. Errors and Java exceptions

Expected failures use a versioned little-endian response frame with stable numeric status codes.
Its fixed 32-byte header is `RMF1`, ABI version, header length, status, payload length, echoed
request ID and eight reserved zero bytes, followed by owned operation payload bytes. An invalid
request ID is echoed as zero. Reserved bytes must remain zero and receivers reject inconsistent
lengths. Exception text, component properties and user data are not returned or logged. Invalid
input is rejected before runtime access. Lifecycle and commit errors retain their own typed codes
inside the operation response rather than becoming Java exceptions.

Every JNI call that can raise a Java exception is checked immediately. While an exception is
pending, the shim performs only JNI-permitted cleanup and returns so ART can propagate it. It
never clears or replaces an exception merely to continue processing.

### 6. Panic containment and unsafe ownership

Each exported entry point is a minimal `unsafe extern "system"` wrapper. Its unsafe block is
limited to JNI access and delegates immediately to safe functions. The wrapper documents pointer,
reference, thread and pending-exception invariants.

Rust work is enclosed by `catch_unwind(AssertUnwindSafe(...))`; a caught Rust panic maps to
`INTERNAL_PANIC` and poisons the affected surface until controlled recovery. No panic payload is
exposed. This does not claim to catch aborting panics or foreign unwinds. No unwind may cross the
JNI boundary.

## Executable contract

`contracts/android-ffi/v1` contains the closed manifest, reviewed request fixtures and binary
corruption corpora. Dependency-free checkers validate versioning, signed transport ranges,
operation-specific handles, thread enforcement, both headers, typed bodies, reserved bytes,
outcome/reason combinations and exact lengths.
An exhaustive bounded campaign flips each bit of seven canonical packets once. Every accepted
mutation must round-trip through the canonical encoder without byte drift; every rejection must
use a registered decoder error. Length-changing corruption remains covered by the reviewed corpus.
They specify pre-runtime admission only; they do not simulate JNI, ART, Rust panic machinery or
Android lifecycle execution.

## Consequences

- The JNI surface is narrow and independently versioned.
- Cross-language ownership is copy-in/copy-out with no pointer handles.
- The transport range is intentionally smaller than internal `u64` identity space.
- Expected errors remain typed data; unexpected Java exceptions retain JVM semantics.
- Android source, CheckJNI tests and real panic containment remain required implementation gates.

## References

- [Android JNI guidance](https://developer.android.com/ndk/guides/jni-tips)
- [Rust FFI and unwinding](https://doc.rust-lang.org/nomicon/ffi.html)
- [Rust `catch_unwind`](https://doc.rust-lang.org/std/panic/fn.catch_unwind.html)
