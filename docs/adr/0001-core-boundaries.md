# ADR-0001: Safe Rust core with ports and thin native adapters

- Status: Accepted
- Date: 2026-09-19

## Context

The framework must be fast, maintainable, testable without a device, and able to use
Android and iOS facilities. A pure native-platform core would duplicate behavior. A
Rust core that imports JNI or platform types would make domain tests platform-bound.

## Decision

Use a platform-independent Rust core and runtime. Runtime crates define narrow traits
as ports. Concrete renderers and platform bridges implement those traits outside the
core. Kotlin and, later, Swift/Objective-C++ remain thin lifecycle and platform adapters.

Begin with a headless renderer contract before Android integration. Use stable Rust,
forbid unsafe code throughout the workspace by default, and permit unsafe only in a
future dedicated FFI crate with crate-local lint exceptions and documented invariants.

## Consequences

- Core behavior is testable on a host without Android tooling.
- Native integration remains replaceable and measurable.
- FFI copying and call frequency must be benchmarked explicitly.
- Some platform capabilities will require deliberately platform-specific ports.
- A full-tree renderer is temporary; it does not imply reconciliation semantics.

## References

- [Cargo workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html)
- [Cargo manifest and `rust-version`](https://doc.rust-lang.org/cargo/reference/manifest.html#the-rust-version-field)
- [Android JNI guidance](https://developer.android.com/ndk/guides/jni-tips)

