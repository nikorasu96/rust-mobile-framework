# ADR-0007: Android adapter module and build topology

- Status: Accepted topology; compiled Android implementation pending
- Date: 2026-09-20
- Depends on: ADR-0003, ADR-0005 and ADR-0006

## Context

The Android slice needs a reproducible build boundary before Kotlin or JNI source is introduced.
Mixing facade, view mutation, JNI safety and runtime orchestration in one module would create a
platform god component. Creating a module for every package would add coordination without a
verified use case. Android Gradle's external native build integration directly supports CMake and
ndk-build, while the native implementation is owned by Cargo.

## Decision

### 1. Three deployable roles

The Android project contains one internal Rust `cdylib`, one publishable Android library and one
sample application. `rmf-android-jni` owns JNI registration and safe routing only. `framework`
owns the public Kotlin facade, main-thread dispatch and host views. `sample` is the composition
root and cannot be a production dependency.

Kotlin never imports domain or runtime implementation concepts. The JNI crate depends inward only
on `rmf-runtime`, which exposes the use cases it needs. Domain, reconciliation and runtime never
depend on Android. Only `JNI_OnLoad` is exported from the native library; all registered native
methods otherwise remain hidden.

### 2. Native artifact flow

Cargo cross-compiles `librmf_android.so` for the explicitly supported Rust targets. A
project-owned Gradle task stages outputs in a generated build directory consumed as `jniLibs`.
The AAR packages those generated libraries; neither `.so` files nor generated directories are
source-controlled. CMake and ndk-build are not used as Cargo wrappers.

The first supported ABIs are `arm64-v8a` for physical devices and `x86_64` for emulator tests.
Thirty-two-bit ABIs are excluded until product evidence justifies their size and testing cost.

### 3. Pinned Android baseline

The first build will use AGP 9.4.0, Gradle 9.6.0, JDK 17, NDK 28.2.13676358, compile/target SDK 37
and minimum SDK 26. The Rust version remains the workspace-pinned 1.85.0. A toolchain upgrade is a
reviewed maintenance change and must pass Rust, Gradle, lint, unit, CheckJNI and device gates.

### 4. Source ownership inside the AAR

The public API is limited initially to `dev.rmf.android.RmfSurfaceHost`. Internal packages may
separate `bridge` transport from `host` view mutation, but they are implementation details within
the single AAR until independent release or dependency pressure is measured. This preserves SRP
without premature Gradle modules.

## Executable enforcement

`platforms/android/architecture.json` closes module IDs, locations, visibility, dependencies,
toolchain versions, ABIs and artifact flow. `scripts/check_android_topology.py` rejects unknown
fields, cycles, outward/native dependency drift, extra exports, publishable samples and generated
artifacts treated as source.

## Consequences

- Consumers receive one AAR and one public Kotlin entry type.
- Unsafe JNI remains isolated from Android UI and domain rules.
- Rust stays the authority for native compilation instead of being hidden behind CMake.
- ABI support and tool versions are explicit compatibility commitments.
- No Android implementation or compatibility claim exists until all compiled gates pass.

## References

- [Android Gradle Plugin 9.4 compatibility](https://developer.android.com/build/releases/agp-9-4-0-release-notes)
- [Android external native build integration](https://developer.android.com/studio/projects/gradle-external-native-builds)
- [Android NDK ABI guidance](https://developer.android.com/ndk/guides/abis)
- [Java versions in Android builds](https://developer.android.com/build/jdks)
