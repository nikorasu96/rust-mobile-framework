# ADR-0009: Public Android Kotlin API v1

- Status: Accepted
- Date: 2026-09-20
- Owners: Android framework adapter maintainers

## Context

ADR-0007 defines one publishable AAR and ADR-0008 defines its surface lifecycle, but neither fixes
the Kotlin declarations consumers compile against. Adding Kotlin source before its toolchain is
available would create an unverified API accidentally. The first implementation therefore needs a
small design baseline that separates public API from JNI and internal orchestration.

Kotlin compatibility has binary, source and behavioral dimensions. Binary and source compatibility
can diverge, default parameters and inferred return types can change JVM signatures, and public
data classes expose generated constructors and `copy` methods. The contract must control those
risks before publication.

## Decision

Version `0.1.0` exposes exactly one final class, `dev.rmf.android.RmfSurfaceHost`. Its public
constructor accepts one `android.view.ViewGroup`, and `close()` implements `AutoCloseable`.
Construction and close may occur on any thread; Android work is marshalled according to ADR-0008,
and close is idempotent.

A companion factory was rejected because Kotlin would emit an additional public companion class,
field and bridge method. The direct constructor keeps the reviewed JVM surface small and explicit.

No public listener, state enum, mutable property, default argument, inline function, type alias,
data class or `@PublishedApi` declaration is included. The initial API does not expose byte arrays,
byte buffers, JNI bridge types, native pointers or either half of a generational handle. Failures
remain internal until their consumer-facing semantics can be specified and tested.

Every declaration and return type will be explicit and documented with KDoc. Compiled Kotlin must
use strict explicit-API mode, warnings as errors, JVM target 17 and ABI validation. AGP 9.4 owns the
built-in Kotlin toolchain; the separate `org.jetbrains.kotlin.android` plugin is forbidden.

Before 1.0, patch releases are additive only. A breaking 0.x change requires a minor version, ADR,
migration guide and changelog. After 1.0, breaking changes require a major version. Binary
compatibility is required; source compatibility is best effort because Kotlin cannot guarantee it
for every call form. Behavioral compatibility is governed by the facade and FFI executable
contracts.

`contracts/android-api/v1/public-api.json` is the design authority. Its JVM descriptors are
reviewed expectations, not generated ABI evidence. Once code exists, compiled `checkKotlinAbi`
output becomes an additional mandatory gate and must agree with this contract.

## Consequences

The first public API is deliberately narrower than React Native and makes no drop-in compatibility
claim. Android consumers receive a stable host ownership primitive while the JNI protocol and
runtime types remain internal. New public capabilities require deliberate schema and semantic
review rather than leaking implementation details.

The contract cannot prove Kotlin/JVM descriptors, Java interop, KDoc generation or AAR contents
until Kotlin and Gradle compilation are available. Those remain explicit build gates.
