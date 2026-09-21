# Android platform boundary

This directory records the compile-gated Android topology accepted by ADR-0007. It does not yet
contain Kotlin, Gradle or JNI source because none can be compiled in the current environment.

The intended production units are deliberately small:

- `native/rmf-android-jni`: one Rust `cdylib`; owns only JNI registration, checked byte transport,
  panic containment and routing into `rmf-runtime`;
- `framework`: one Android library/AAR; owns the public Kotlin facade, main-thread marshalling and
  native view hosting;
- `sample`: an application composition root for emulator/device and accessibility tests.

Rust produces `librmf_android.so` for `arm64-v8a` and `x86_64`. A project-owned Gradle task will
stage those generated outputs under `framework/build/generated/rmfJniLibs` and expose that
directory as a `jniLibs` source. Generated libraries are never committed. CMake and ndk-build are
not inserted as wrappers around Cargo: Android Gradle's external native build integration is for
those build systems, while Rust remains authoritative for the native artifact.

`architecture.json` is the machine-readable authority. Run:

```text
python3 scripts/check_android_topology.py
```

Passing this check claims only a reviewed topology, pinned tool versions and dependency rules. It
does not claim an AAR, compiled Rust target, Gradle sync, CheckJNI or device execution.

The future `framework` facade lifecycle is fixed separately by ADR-0008 and the executable
contract under `contracts/android-facade/v1`. It covers any-thread request marshalling,
create/close races, idempotent disposal and stale callback rejection. Run:

```text
python3 scripts/check_android_facade_fixtures.py
python3 scripts/check_android_facade_exhaustive.py
```

Passing it still does not claim Kotlin compilation or Android lifecycle integration.

ADR-0009 and `contracts/android-api/v1/public-api.json` define the only intended public Kotlin
class and its two JVM signatures. The contract forbids JNI transport details and internal runtime
types from leaking into the AAR. Run:

```text
python3 scripts/check_android_public_api.py
```

The descriptors remain design expectations until strict Kotlin compilation and `checkKotlinAbi`
can inspect the produced bytecode.

ADR-0010 and `contracts/android-container/v1` define the internal boundary between that facade
and an application-owned `ViewGroup`. The contract allows one current host, attaches and removes
only the framework-owned root, and isolates stale results from a replacement host. Run:

```text
python3 scripts/check_android_container_fixtures.py
python3 scripts/check_android_container_exhaustive.py
```

Passing these scenarios does not claim that `ViewGroup.addView` or `removeView` ran on Android.

ADR-0011 and `contracts/android-host/v1` define the orchestration between those boundaries. Root
attachment completes before native creation; callbacks pass the surface-handle gate before the
facade gate; terminal cleanup targets only the current host. Run:

```text
python3 scripts/check_android_host_composition.py
```

This executable specification is not a compiled Android adapter or concurrency test.
