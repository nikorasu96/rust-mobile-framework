# Compatibility matrix

This file records observed capability, not branding or claimed drop-in compatibility.

| Capability | Status | Evidence | Important gap |
| --- | --- | --- | --- |
| Declarative tree model | Experimental | `rmf-core` tests | Only `View` and `Text` |
| Declarative candidate validation | Rust implementation | `rmf-core::candidate`, typed schema, defensive-limit tests and headless composition root | No TypeScript facade or Android integration |
| Initial tree reconciliation | Rust implementation | `rmf-reconciliation` initial-mount contract tests | No runtime host application |
| Stable-tree property updates | Rust implementation | identity-preservation, set/remove and atomic-rejection Rust tests | No general multi-change reconciliation |
| Keyed child reorder | Partial Rust implementation | single-move identity, direction and atomic multi-move rejection tests | One move per sibling list; no general reorder |
| Keyed child insertion | Partial Rust implementation | middle/append identity and atomic-limit Rust tests | One keyed insertion per sibling list; no unkeyed or multiple insertion |
| Keyed child removal | Partial Rust implementation | identity, subtree ordering and atomic-limit Rust tests | One keyed removal per sibling list; no unkeyed or multiple removal |
| Keyed child replacement | Partial Rust implementation | kind/key replacement, fresh identity, ordering and atomic-limit Rust tests | One keyed replacement per sibling list; no unkeyed or multiple replacement |
| Runtime mount port | Legacy | `rmf-runtime` legacy contract test | Caller-identified full-tree bootstrap remains only in renderer/runtime tests pending removal |
| Commit application and recovery | Rust implementation | `BatchApplier`, `SnapshotRemounter`, `CommitCoordinator`, Rust contract tests, ADR-0004, eight reviewed fixtures, 800 generated actions and 567 exhaustive transitions | No platform adapter, real UI-thread execution or concurrent executor stress |
| Surface lifecycle | Rust implementation | `Runtime` lifecycle API, `rmf-runtime::surface`, Rust unit/integration tests, ADR-0005, six fixtures, 800 generated actions and 1,008 exhaustive transitions | No Android adapter, concurrent executor stress or unbounded proof |
| Android FFI boundary | Executable contract | ADR-0006, ten admission fixtures, 34 reviewed binary cases and 2,128 exhaustive one-bit mutations | Only click and three commit outcomes are modeled; no compiled JNI, Kotlin, CheckJNI or emulator evidence |
| Android build topology | Executable contract | ADR-0007 and closed module/toolchain/ABI manifest | No Gradle project, AAR or cross-compiled native library yet |
| Android Kotlin facade lifecycle | Executable contract | ADR-0008, twelve reviewed scenarios and 4,832 bounded exhaustive transitions | No compiled Kotlin, Android lifecycle-owner integration or unbounded proof |
| Android public Kotlin API | Design contract | ADR-0009 and closed source/JVM signature manifest | Descriptors are reviewed expectations; no compiled ABI dump or AAR evidence |
| Android container ownership | Executable contract | ADR-0010, eleven reviewed scenarios and 19,926 bounded transitions | No compiled `ViewGroup` adapter, Robolectric, emulator, device evidence or unbounded proof |
| Android host composition | Executable contract | ADR-0011, seven reviewed scenarios and 21 composed actions | No compiled Kotlin/JNI adapter, Android hierarchy execution or concurrent stress evidence |
| Deterministic headless host | Rust implementation | atomic mutation/remount adapter, logical host metrics, Rust contracts, executable example and committed-path benchmark | Diagnostic host only; not visual rendering |
| Android rendering | Not started | — | No JNI/Kotlin layer |
| TypeScript/React API | Not started | — | No JS engine or bindings |
| Reconciliation | Partial Rust implementation | ADR-0002, compiled initial/property/move/insertion/removal/replacement contracts, runtime batch application and recovery, thirty-one v1 fixtures and 200 generated transitions | No multiple structural changes or general reorder |
| Typed properties | Executable contract | Versioned `View`/`Text` schema plus contract fixtures | Bootstrap Rust tree has no property set |
| Layout and styling | Not started | — | No layout engine |
| Events and accessibility | Contract seed | Typed `CLICK` FFI body with node identity and sequence | No listener, native dispatch, accessibility semantics or state integration |
| iOS | Deferred | — | Begins after Android gates |
