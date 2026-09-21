# Compatibility matrix

This file records observed capability, not branding or claimed drop-in compatibility.

| Capability | Status | Evidence | Important gap |
| --- | --- | --- | --- |
| Declarative tree model | Experimental | `rmf-core` tests | Only `View` and `Text` |
| Declarative candidate validation | Rust implementation | `rmf-core::candidate`, typed schema and defensive-limit tests | No TypeScript facade or reconciled committed snapshot |
| Runtime mount port | Experimental | `rmf-runtime` contract test | Full-tree mount only |
| Commit application and recovery | Executable contract | ADR-0004, eight reviewed fixtures, 800 generated actions and 567 exhaustive transitions | No compiled mutation host port or unbounded proof |
| Surface lifecycle | Rust implementation | `Runtime` lifecycle API, `rmf-runtime::surface`, Rust unit/integration tests, ADR-0005, six fixtures, 800 generated actions and 1,008 exhaustive transitions | No Android adapter, concurrent executor stress or unbounded proof |
| Android FFI boundary | Executable contract | ADR-0006, ten admission fixtures, 34 reviewed binary cases and 2,128 exhaustive one-bit mutations | Only click and three commit outcomes are modeled; no compiled JNI, Kotlin, CheckJNI or emulator evidence |
| Android build topology | Executable contract | ADR-0007 and closed module/toolchain/ABI manifest | No Gradle project, AAR or cross-compiled native library yet |
| Android Kotlin facade lifecycle | Executable contract | ADR-0008, twelve reviewed scenarios and 4,832 bounded exhaustive transitions | No compiled Kotlin, Android lifecycle-owner integration or unbounded proof |
| Android public Kotlin API | Design contract | ADR-0009 and closed source/JVM signature manifest | Descriptors are reviewed expectations; no compiled ABI dump or AAR evidence |
| Android container ownership | Executable contract | ADR-0010, eleven reviewed scenarios and 19,926 bounded transitions | No compiled `ViewGroup` adapter, Robolectric, emulator, device evidence or unbounded proof |
| Android host composition | Executable contract | ADR-0011, seven reviewed scenarios and 21 composed actions | No compiled Kotlin/JNI adapter, Android hierarchy execution or concurrent stress evidence |
| Deterministic headless output | Experimental | adapter regression tests | Not visual rendering |
| Android rendering | Not started | — | No JNI/Kotlin layer |
| TypeScript/React API | Not started | — | No JS engine or bindings |
| Reconciliation | Executable contract | ADR-0002, thirty-one v1 fixtures, independent batch application and 200 generated transitions | No compiled Rust implementation |
| Typed properties | Executable contract | Versioned `View`/`Text` schema plus contract fixtures | Bootstrap Rust tree has no property set |
| Layout and styling | Not started | — | No layout engine |
| Events and accessibility | Contract seed | Typed `CLICK` FFI body with node identity and sequence | No listener, native dispatch, accessibility semantics or state integration |
| iOS | Deferred | — | Begins after Android gates |
