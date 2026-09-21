# Roadmap

## Phase 0 — Foundation

- [x] Record dependency direction and native-boundary decision.
- [x] Create a pinned Rust workspace with inherited lints.
- [x] Implement validated declarative tree and renderer port.
- [x] Add deterministic headless adapter and contract-oriented tests.
- [x] Add automated architecture-boundary verification.
- [x] Establish dependency-free benchmark harness and provisional host budgets.
- [ ] Capture the first compiled benchmark baseline on identified hardware.

## Phase 1 — Tree and reconciliation

- [x] Specify immutable tree, property, identity and mutation semantics in ADR-0002.
- [x] Add language-independent golden fixtures and executable reference oracle.
- [x] Add versioned component schemas and enforce property support and tagged types.
- [ ] Implement keyed reconciliation with deterministic mutation batches.
- [x] Add deterministic generated tests for reconciliation invariants.
- [x] Define the reconciliation crate boundary, ownership and public type contract.
- [x] Implement the validated declarative candidate model without caller-assigned runtime IDs.
- [x] Implement deterministic initial-mount reconciliation and immutable snapshots in Rust.
- [x] Preserve identities and reconcile properties on structurally stable trees.
- [x] Implement and benchmark deterministic single-child keyed movement in Rust.
- [x] Specify commit application, promotion and full-remount recovery semantics.
- [x] Add deterministic generated tests for commit-state safety invariants.
- [x] Exhaustively explore bounded commit-state transitions and recovery boundaries.
- [x] Specify generational surface creation, disposal and stale-callback rejection.
- [x] Add deterministic generated tests for surface lifecycle invariants.
- [x] Exhaustively explore bounded lifecycle states, handles and isolation invariants.
- [x] Implement and compile the generational surface registry in Rust.
- [x] Route creation, disposal and callback admission through the Rust runtime use case.
- [ ] Implement and compile the reconciliation crate against every v1 contract.
- [ ] Add coverage-guided fuzzing once the compiled Rust reconciler exists.
- [ ] Benchmark general update/remove workloads at representative tree sizes.

## Phase 2 — Android vertical slice

- [x] Specify stable FFI boundary, ownership, threading, panic, and error policy.
- [x] Define Android module ownership, pinned build topology and initial ABI set.
- [x] Specify the public Kotlin surface lifecycle and main-thread contract.
- [x] Exhaustively explore bounded Kotlin facade interleavings and safety invariants.
- [x] Freeze the initial public Kotlin declarations and compatibility policy.
- [x] Specify exclusive Android container ownership, detach and stale-result cleanup.
- [x] Exhaustively explore bounded container mount, close and replacement interleavings.
- [x] Compose facade, container ownership and generational surface lifecycles.
- [ ] Add dedicated Rust Android adapter and minimal Kotlin lifecycle shell.
- [ ] Mount `View` and `Text` on an emulator/device through JNI.
- [ ] Propagate one click event back to the runtime.
- [ ] Add Android integration and accessibility assertions.

## Later phases

Layout, styling, text, images, events, state, navigation, accessibility, networking,
storage, native modules, animation, gestures, TypeScript API, CLI, hot reload,
debugging, packaging, performance hardening, security hardening, and finally iOS.

Every checkbox needs executable acceptance evidence. A label alone is not parity.
