# Changelog

All notable changes follow semantic versioning once a public API is released.

## Unreleased

- Added workspace quality policy and pinned Rust toolchain.
- Added validated platform-independent declarative tree.
- Added renderer port, runtime mount use case, and deterministic headless adapter.
- Added architecture ADR, roadmap, compatibility matrix, and debt register.
- Added an executable architecture-boundary check with four regression tests.
- Added a dependency-free 1,000-node performance gate and documented provisional budgets.
- Accepted ADR-0002 for immutable properties, identity and deterministic reconciliation.
- Added reconciliation v1 golden fixtures and a dependency-free executable oracle.
- Extended reconciliation v1 with property removal, subtree deletion and stale revisions.
- Added typed property validation and defensive-limit fixtures to reconciliation v1.
- Added a versioned component-property registry with fail-closed kind, support and type checks.
- Added closed candidate-node validation and a configurable direct-child limit.
- Replaced quadratic keyed matching in the reference oracle with a per-sibling hash index.
- Added fail-closed reconciliation-envelope, revision, allocator and limit validation.
- Added committed-tree structure, identity uniqueness and allocator continuity validation.
- Split the executable reconciliation specification into validation, oracle and runner modules.
- Added an independent host-tree mutation applier for every successful reconciliation batch.
- Added fixed-seed generated reconciliation sequences with stateful invariant checks.
- Accepted ADR-0003 for the reconciliation crate boundary, ownership and public type contract.
- Accepted ADR-0004 and added executable commit-application and recovery fixtures.
- Added fixed-seed generated commit-state sequences with promotion and recovery invariants.
- Added bounded exhaustive commit-state exploration over every reachable state/action pair.
- Accepted ADR-0005 and added executable generational surface-lifecycle fixtures.
- Added fixed-seed generated surface lifecycle sequences with non-reuse and isolation checks.
- Added bounded exhaustive surface lifecycle exploration with shared safety invariants.
- Accepted ADR-0006 and added an executable, versioned Android JNI admission contract.
- Added strict response/payload frame decoders and a nineteen-case binary corruption corpus.
- Added fixed-size typed click-event and commit-result bodies with a fifteen-case boundary corpus.
- Added exhaustive single-bit mutation testing for canonical Android FFI packets.
- Accepted ADR-0007 with a machine-checked Android module, toolchain, ABI and artifact topology.
- Accepted ADR-0008 with an executable main-thread and lifecycle contract for the public Kotlin surface facade.
- Added bounded exhaustive exploration of Kotlin facade interleavings with shared lifecycle invariants.
- Accepted ADR-0009 with a machine-checked minimal public Kotlin API and compatibility policy.
- Accepted ADR-0010 with executable exclusive-container ownership and exact-root detach semantics.
- Added bounded exhaustive exploration of Android container ownership with shared safety invariants.
- Accepted ADR-0011 and added executable composition of Android facade, container and surface lifecycles.
- Implemented the ADR-0005 generational surface registry in safe Rust with CI build gates.
- Integrated surface creation, disposal and callback admission into the Rust runtime use case.
- Added a runtime-ID-free declarative candidate model and typed validation in `rmf-core`.
- Added deterministic initial-mount reconciliation and immutable snapshots in Rust.
- Added property-only incremental reconciliation with stable runtime identity preservation.
- Added linear-time single-child keyed movement with deterministic identity preservation.
- Added linear-time single-child keyed insertion with deterministic identity preservation.
