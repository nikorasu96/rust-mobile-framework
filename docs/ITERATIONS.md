# Iteration log

## 2026-09-19 — Foundation and first headless vertical slice

### Acceptance criteria

- A virtual Cargo workspace expresses inward dependency direction.
- The platform-independent core rejects invalid node identities and tree structures.
- Runtime orchestration targets a renderer trait, not a concrete adapter.
- A deterministic headless adapter renders a valid tree through the public runtime API.
- Tests cover the domain invariants, runtime delegation, and adapter output.
- Architecture, roadmap, compatibility, and technical debt are explicit.

### Delivered

- Four workspace packages: two inward crates, one adapter, and one composition example.
- Seven behavioral tests in source: four core, one runtime, and two adapter tests.
- No third-party runtime dependencies and no unsafe blocks.
- Central lints, pinned MSRV/toolchain, release profile, and dependency policy.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| TOML parsing | Passed | All five Cargo manifests plus tool/policy TOML parsed locally |
| Forbidden-token scan | Passed | No `TODO`, `FIXME`, `.unwrap()`, `.expect()`, or unsafe block |
| Dependency-direction review | Passed | Core has no dependencies; runtime depends only on core; adapter points inward |
| `cargo fmt --check` | Blocked | Rust toolchain is absent from the execution environment |
| `cargo clippy` | Blocked | Rust toolchain is absent from the execution environment |
| `cargo test` | Blocked | Rust toolchain is absent from the execution environment |
| `cargo doc` | Blocked | Rust toolchain is absent from the execution environment |
| `cargo deny check` | Blocked | Cargo and `cargo-deny` are absent |

### Risk review

- The source is structurally reviewed but cannot yet be described as compiled.
- Rust 1.85.0 is intentional: it is the first stable release supporting Edition 2024.
- Android work is deferred until the core build gate passes.

### Next increment

Run all Rust gates in a provisioned environment, correct any compiler or lint findings,
then add machine-enforced dependency boundaries and a small benchmark harness. Do not
start JNI while TD-001 remains open.

## 2026-09-19 — Machine-enforced architecture boundaries

### Acceptance criteria

- Workspace packages are classified into explicit architecture layers.
- Dependencies may point inward or remain within a layer, never outward.
- Unclassified workspace packages fail closed.
- The core cannot silently acquire a third-party Cargo dependency.
- The checker itself has regression tests for allowed and forbidden graphs.

### Delivered

- Added `scripts/check_architecture.py` using only Python 3.11 standard library.
- Added four isolated regression tests using temporary fixture workspaces.
- Closed TD-002 and documented the deliberately strict core dependency policy.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Architecture check on repository | Passed | All four current packages classified; every internal edge points inward |
| Architecture checker tests | Passed | Four tests cover inward, outward, unclassified and external-core cases |
| TOML parsing | Passed | Eight TOML files parsed with Python `tomllib` |
| Rust gates | Blocked | Rust toolchain remains unavailable; package provisioning is restricted |

### Next increment

Add a dependency-free benchmark executable for tree validation and headless mounting,
with explicit latency and memory budgets. Keep Android/JNI blocked until Rust gates run.

## 2026-09-19 — Reproducible foundation performance gate

### Acceptance criteria

- Benchmark code remains outside core/runtime and depends inward through public APIs.
- A deterministic 1,000-node workload measures validation and headless mounting.
- Explicit latency and frame-size budgets fail the executable when exceeded.
- Documentation distinguishes provisional host guardrails from mobile product SLOs.

### Delivered

- Added the dependency-free `rmf-bench` composition package.
- Added validation <= 1 ms, mount <= 2 ms and frame <= 2 MiB provisional gates.
- Added performance methodology, limitations and rules for comparable results.
- Extended architecture enforcement and its regression suite for benchmark packages.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Architecture check | Passed | Benchmark depends inward; no core/runtime outward edge |
| Architecture checker tests | Passed | Five regression cases |
| Benchmark source review | Passed | Fixed workload, typed failures, no external dependency |
| Benchmark execution | Blocked | Rust toolchain remains unavailable |
| Rust gates | Blocked | Rust toolchain remains unavailable |

### Next increment

Specify an immutable property model and reconciliation mutation protocol in ADR form,
then implement only after the unresolved Rust build gate can be executed.

## 2026-09-19 — Property and reconciliation contract

### Acceptance criteria

- Separate public keys from runtime-owned node identities.
- Define immutable property values without JSON, platform objects or executable closures.
- Define a deterministic, revision-guarded host mutation vocabulary and ordering.
- Address concurrency, stale events, host failure, complexity and defensive limits.
- State required tests and migration from the bootstrap API before implementation.

### Delivered

- Accepted ADR-0002 with immutable committed trees and structural sharing direction.
- Defined typed property schemas and canonical equality requirements.
- Defined six mutation operations plus validation, ordering and recovery semantics.
- Recorded the bootstrap identity API mismatch as high-priority TD-005.
- Updated architecture, roadmap and compatibility status without claiming implementation.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Architecture check | Passed | Existing dependency graph remains inward-only |
| Architecture checker tests | Passed | Five regression cases |
| Contract consistency review | Passed | Identity, ordering, revision and failure rules are explicit |
| Reconciliation implementation | Deferred | Rust build gate remains unresolved |

### Next increment

Prepare executable, language-independent reconciliation fixtures that encode ADR-0002
golden cases. Do not modify the Rust tree API or begin Android until compilation works.

## 2026-09-19 — Executable reconciliation contract v1

### Acceptance criteria

- Fixtures are portable JSON and contain no Rust-specific serialization assumptions.
- A deterministic reference oracle verifies exact mutations and committed identities.
- Initial mount, property update, keyed reorder, type replacement and duplicate keys are covered.
- The production Rust API remains unchanged while its build gate is unavailable.

### Delivered

- Added five reconciliation v1 golden fixtures and format documentation.
- Added a standard-library Python oracle for identity allocation, property deltas,
  keyed matching, ordered host mutations and typed validation errors.
- Updated compatibility status to executable contract without claiming Rust implementation.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | Five exact fixture comparisons |
| Architecture check | Passed | No production dependency change |
| Architecture checker tests | Passed | Five regression cases |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

### Next increment

Extend the contract with subtree deletion, stale-revision rejection and property removal,
then prepare Rust implementation only after the compiler gate is available.

## 2026-09-19 — Reconciliation deletion and revision contracts

### Acceptance criteria

- Property removal produces an explicit, sorted removal list.
- Removing a subtree detaches nodes and deletes descendants before ancestors.
- A base revision different from the committed revision fails before mutations.
- Existing contract cases remain byte-for-byte deterministic.

### Delivered

- Added property-removal, subtree-removal and stale-revision fixtures.
- Expanded reconciliation v1 from five to eight executable cases.
- Documented the covered contract surface and compatibility evidence.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | Eight exact fixture comparisons |
| Architecture check | Passed | No production dependency change |
| Architecture checker tests | Passed | Five regression cases |
| JSON/TOML parsing | Passed | All contract and project metadata parsed |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

### Next increment

Add executable property-value validation and defensive limit cases for strings, depth,
node counts and operation counts without expanding the production Rust API prematurely.

## 2026-09-19 — Property validation and defensive limits

### Acceptance criteria

- Accept the closed v1 bool, i64, finite f64 and UTF-8 string value family.
- Reject malformed or non-finite property values before identity allocation.
- Enforce configurable string-byte, depth, node and operation limits.
- Preserve all prior mutation and validation contracts.

### Delivered

- Added validation for positive decimal property IDs and closed tagged values.
- Added UTF-8 byte counting, signed 64-bit range and finite-float checks.
- Added one positive all-types fixture plus five negative limit/value fixtures.
- Expanded reconciliation v1 from eight to fourteen executable cases.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | Fourteen exact fixture comparisons |
| Property family | Passed | bool, i64, finite f64 and UTF-8 string accepted |
| Defensive failures | Passed | Invalid value and four configurable limits fail closed |
| Architecture/tests/metadata | Passed | Architecture, five tests, JSON and TOML |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

### Next increment

Define and execute component property schemas so a valid property ID/value pair can still
be rejected when unsupported by a specific component kind.

## 2026-09-19 — Executable component property schemas

### Acceptance criteria

- Resolve every property against a versioned component-specific registry.
- Reject unknown component kinds, unsupported properties and mismatched tagged types.
- Validate the registry itself before executing any reconciliation case.
- Preserve all fourteen prior reconciliation contracts.

### Delivered

- Added a versioned schema registry for the provisional `View` and `Text` surface.
- Added fail-closed validation for schema shape, property IDs, names and value types.
- Added three negative fixtures for unknown kinds, unsupported properties and type mismatch.
- Updated the positive type fixture to exercise both registered component schemas.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | Seventeen exact fixture comparisons |
| Component schema validation | Passed | Version, descriptor, ID, name and type checks execute first |
| Schema enforcement | Passed | Three distinct typed rejection paths |
| Prior contracts | Passed | All fourteen prior fixtures remain green |
| Python regression tests | Passed | Nine tests, including four direct schema-loader cases |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

### Next increment

Add executable validation for maximum children per node and malformed candidate structure,
including missing fields and unexpected fields, before translating this contract to Rust.

## 2026-09-19 — Closed candidate structure and child limits

### Acceptance criteria

- Treat candidate nodes as closed objects with four required fields.
- Reject missing, unexpected and incorrectly typed fields before identity allocation.
- Enforce a configurable maximum number of direct children per node.
- Preserve every existing component-schema and reconciliation contract.

### Delivered

- Added recursive structural validation for `kind`, `key`, `properties` and `children`.
- Added a default 10,000-child defensive limit with per-execution override support.
- Added four negative fixtures for child count, missing fields, unexpected fields and
  invalid field types.
- Expanded reconciliation v1 from seventeen to twenty-one executable cases.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | Twenty-one exact fixture comparisons |
| Closed node structure | Passed | Missing, extra and invalid fields fail with a typed error |
| Direct-child limit | Passed | Limit failure occurs before allocation or mutations |
| Prior contracts | Passed | All seventeen prior fixtures remain green |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

### Next increment

Replace the reference oracle's keyed-sibling scan with a linear index and add a wide-list
determinism regression so the executable specification reflects ADR-0002's complexity rule.

## 2026-09-19 — Indexed keyed-sibling matching

### Acceptance criteria

- Build at most one key index for each previous sibling list.
- Perform one indexed lookup for each keyed candidate instead of scanning all old siblings.
- Preserve identity and mutation output for all existing fixtures.
- Exercise a wide reversed list twice to verify deterministic, unique selection.

### Delivered

- Extracted keyed identity selection into a small pure function.
- Replaced the nested keyed scan with a key-to-old-index table.
- Added a direct regression using 2,048 reversed keyed siblings.
- Documented that this is complexity-shape evidence, not a Rust latency benchmark.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | All twenty-one exact outputs unchanged |
| Wide sibling regression | Passed | 2,048 identities selected uniquely in reverse order twice |
| Python regression tests | Passed | Ten direct tests |
| Architecture and metadata | Passed | No dependency or contract-format change |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

Risk recorded: matching is now expected-linear, but applying many move operations to the
oracle's list representation can still be quadratic. TD-006 tracks this separately so the
production Rust reconciler cannot inherit it without measurement and design review.

### Next increment

Validate the reconciliation transaction envelope: closed fixture fields, monotonic
revisions, positive allocator state and well-formed defensive limit overrides.

## 2026-09-19 — Reconciliation transaction envelope

### Acceptance criteria

- Separate test-only fixture metadata from runtime request fields.
- Reject missing or unexpected envelope fields before tree processing.
- Require non-negative base revisions and a target revision exactly one step ahead.
- Require a positive allocator identity and known, positive integer limit overrides.

### Delivered

- Added explicit fixture and transaction field sets with fail-closed validation.
- Added typed failures for revision, allocator and limit violations.
- Added five negative fixtures covering every new rejection category.
- Expanded reconciliation v1 from twenty-one to twenty-six executable cases.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | Twenty-six exact fixture comparisons |
| Closed envelope | Passed | Missing and unexpected fields rejected |
| Revision/allocator validation | Passed | Invalid states fail before candidate traversal |
| Defensive limits | Passed | Unknown, boolean, zero and negative values are rejected by the validator |
| Prior contracts | Passed | All twenty-one prior fixtures remain green |
| Python regression tests | Passed | Eleven tests, including all invalid limit shapes |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

### Next increment

Validate committed-tree structure and identity invariants, including unique positive
`NodeId` values and an allocator strictly above every identity in the previous tree.

## 2026-09-20 — Committed-tree identity invariants

### Acceptance criteria

- Validate the closed shape and non-negative revision of the committed tree.
- Require every runtime node identity to be positive and globally unique.
- Revalidate component schemas, structural limits and sibling-key uniqueness.
- Require the allocator to be strictly greater than every committed identity.

### Delivered

- Added recursive committed-tree validation before stale checks or candidate traversal.
- Added global identity tracking and maximum-identity calculation.
- Added five negative fixtures for duplicate/non-positive identities, invalid structure,
  invalid committed revision and allocator overlap.
- Expanded reconciliation v1 from twenty-six to thirty-one executable cases.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | Thirty-one exact fixture comparisons |
| Identity uniqueness | Passed | Duplicate and non-positive IDs rejected |
| Allocator continuity | Passed | Reuse of the maximum committed ID rejected |
| Closed committed state | Passed | Unexpected fields and invalid revisions rejected |
| Prior contracts | Passed | All twenty-six prior fixtures remain green |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

Maintainability review recorded TD-007 because the cohesive executable specification now
contains 522 lines. No further contract behavior will be added until it is split.

### Next increment

Refactor the executable specification into validation, reconciliation and fixture-runner
modules without changing any of the thirty-one golden outputs or public contract files.

## 2026-09-20 — Reconciliation specification modularization

### Acceptance criteria

- Separate validation, reconciliation and fixture execution responsibilities.
- Preserve direct-script and Python-module execution modes.
- Keep every golden output and typed error unchanged.
- Close TD-007 before adding more contract behavior.

### Delivered

- Reduced the fixture runner from 522 to 50 lines.
- Extracted a 274-line validation module and a 234-line reconciliation oracle.
- Updated direct tests to import the narrow module that owns each behavior.
- Documented module ownership beside the executable contract.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Direct script execution | Passed | Thirty-one exact fixture comparisons |
| Module execution | Passed | Same thirty-one comparisons through `python -m` |
| Python regression tests | Passed | Eleven direct tests |
| Golden compatibility | Passed | No fixture or expected output changed |
| Maintainability gate | Passed | Largest module is 274 lines; TD-007 closed |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

### Next increment

Add an independent mutation-batch model applier and verify that applying every successful
batch to the previous model reproduces the committed tree exactly.

## 2026-09-20 — Independent mutation-batch application

### Acceptance criteria

- Apply every successful batch without calling reconciliation-oracle internals.
- Enforce operation preconditions for identity, attachment, index and deletion state.
- Compare the resulting host-visible tree with the committed host projection.
- Keep declarative keys outside the host model because no mutation transports them.

### Delivered

- Added a standalone host-tree model for all six v1 mutation operation types.
- Seeded prior committed trees and validated reachability after each complete batch.
- Integrated independent application into both fixture-runner entry modes.
- Added a regression proving an incorrect move source is rejected.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reconciliation golden fixtures | Passed | Thirty-one exact fixture comparisons |
| Independent batch application | Passed | All seven successful v1 batches reproduce their host projection |
| Mutation preconditions | Passed | Invalid move source rejected independently |
| Python regression tests | Passed | Twelve direct tests |
| Architecture and metadata | Passed | Boundary, JSON and TOML checks remain green |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

Keys are intentionally absent from this equality check: they select reconciler identity but
the v1 mutation vocabulary does not expose them to the host. The checker therefore compares
only state that can be reconstructed from operations rather than inventing an implicit side
channel.

### Next increment

Add deterministic generated reconciliation sequences with fixed seeds and assert identity,
reachability and independent-application invariants without adding external dependencies.

## 2026-09-20 — Deterministic generated reconciliation sequences

### Acceptance criteria

- Exercise stateful reconciliation across reproducible multi-revision surfaces.
- Cover creation, removal, keyed reordering, kind replacement and property changes.
- Reject identity reuse and verify identity preservation for matched nodes.
- Apply every generated batch through the independent host model.

### Delivered

- Added eight fixed-seed campaigns with twenty-five revisions each.
- Added bounded tree evolution using only the versioned `View` and `Text` schemas.
- Added uniqueness, positivity, allocator continuity and non-reuse assertions for `NodeId`.
- Added a regression that executes the same reduced campaign twice and compares metrics
  and the complete result digest.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Generated transitions | Passed | Two hundred stateful revisions across eight seeds |
| Independent application | Passed | Every generated batch reproduces the committed host projection |
| Identity invariants | Passed | Preservation, uniqueness, positivity and lifetime non-reuse |
| Reproducibility | Passed | Repeated fixed-seed campaign returns the same SHA-256 digest |
| Mutation coverage | Passed | All six operations exercised across 3,695 generated mutations |
| Golden compatibility | Passed | All thirty-one reviewed fixtures remain unchanged |
| Rust implementation | Deferred | Rust toolchain remains unavailable |

The generated campaign is deterministic property-style testing, not coverage-guided fuzzing.
It introduces no dependency and records a digest so failures can be replayed precisely. Its
sampler is built only on the standard generator's documented compatible `random()` sequence;
bounded selection and Fisher-Yates shuffling are owned by the test harness.
The accepted campaign created 573 identities and produced digest
`2e286269a87799d32d44959f384b836d914da7d6c67138f203e4b3375bf028bc`.

### Next increment

Define the Rust reconciliation crate boundary and public types from ADR-0002 without yet
implementing the algorithm, including dependency rules and compile-gated acceptance criteria.

## 2026-09-20 — Reconciliation crate boundary

### Acceptance criteria

- Assign declarative, reconciliation, orchestration and adapter ownership explicitly.
- Define a narrow Rust type surface that prevents forged identities and committed state.
- Document immutability, threading, errors, ABI exclusions and extension policy.
- Enforce dependency direction before introducing the crate source.

### Delivered

- Accepted ADR-0003 with the normative public type and method shape.
- Defined `rmf-core <- rmf-reconciliation <- rmf-runtime` as the inward dependency chain.
- Kept reconciliation concrete and stateless instead of introducing a premature strategy trait.
- Added architecture classifications and regression tests for both allowed and forbidden edges.
- Defined nine compile-gated acceptance checks that must pass when source is introduced.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Architecture boundary | Passed | Reconciliation-to-core dependency accepted |
| Dependency inversion | Passed | Core-to-reconciliation dependency rejected |
| Existing architecture | Passed | Sixteen total regression tests remain green |
| Golden and generated contracts | Preserved | No executable contract or fixture changed |
| Rust implementation | Deferred | No uncompiled crate source introduced while TD-001 is open |

The boundary uses opaque positive identities and immutable shared ownership based on standard
Rust types. It deliberately makes no stable ABI promise; Android DTO conversion remains a
future FFI-adapter responsibility.

### Next increment

Specify the commit-application runtime port and surface failure-state machine so host success,
promotion and full-remount recovery are unambiguous before Android or JNI code is introduced.

## 2026-09-20 — Commit application and recovery contract

### Acceptance criteria

- Promote a prepared snapshot only after confirmed host success.
- Distinguish safe pre-mutation rejection from possibly partial failure.
- Block commits while applying or while recovery is required.
- Restore only the last confirmed snapshot through an explicit full remount.

### Delivered

- Accepted ADR-0004 with narrow batch-application and remount ports.
- Defined `Ready`, `Applying`, `Failed` and `Remounting` surface states.
- Added a closed, dependency-free executable state-transition model.
- Added eight fixtures covering promotion, stale and invalid revisions, safe rejection,
  partial failure, reentrancy, remount success, remount failure and retry.
- Added four direct regression tests for fail-closed envelopes, revisions and recovery behavior.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Commit fixtures | Passed | Eight exact transition sequences |
| Promotion atomicity | Passed | Target revision appears only after host success |
| Partial failure isolation | Passed | New commit rejected until recovery |
| Recovery | Passed | Confirmed revision restored before retry |
| Existing contracts | Preserved | Reconciliation golden and generated suites unchanged |
| Rust implementation | Deferred | Runtime port source remains compile-gated |

The model is an executable specification, not a simulated native renderer. Adapter-specific
behavior remains outside the runtime contract and will require Android integration tests.

### Next increment

Add deterministic generated transition sequences for the commit state machine and verify that
no action can promote without host success or escape a failed state without remount success.

## 2026-09-20 — Deterministic generated commit-state sequences

### Acceptance criteria

- Exercise every action type through reproducible multi-step surface lifecycles.
- Prove that only confirmed host success can advance the committed revision.
- Prove that a failed surface cannot accept a commit or return to ready without remount success.
- Preserve the reviewed fixtures and existing reconciliation campaigns.

### Delivered

- Added eight fixed-seed campaigns with one hundred actions each.
- Added transition-local invariants for promotion, rejection, partial failure and recovery.
- Extracted the stable sampler so both generated suites share one deterministic primitive.
- Added reproducibility regression coverage for the complete metrics and digest.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Generated actions | Passed | 800 transitions covering all seven action types |
| Promotion atomicity | Passed | 57 promotions, each following `host_applied` exactly |
| Partial-failure isolation | Passed | 63 host failures preserve the confirmed revision |
| Recovery isolation | Passed | 62 returns to ready occur only after remount success |
| Reproducibility | Passed | SHA-256 `4e02c976f3826067d8b93d96a93b3cddd45f8773e0eddb5d3839181e3a60030b` |
| Reviewed compatibility | Passed | Eight commit and thirty-one reconciliation fixtures unchanged |
| Rust implementation | Deferred | Runtime port source remains compile-gated while Cargo is unavailable |

The campaign is deterministic property-style testing, not a native-host simulation or
coverage-guided fuzzing. Its sampler depends only on the standard generator's compatible
`random()` sequence and uses owned bounded selection logic.

### Next increment

Add bounded exhaustive exploration of the commit-state model and prove that no reachable trace
can enter an invalid state, promote without host success or bypass recovery.

## 2026-09-20 — Bounded exhaustive commit-state exploration

### Acceptance criteria

- Enumerate every action class from every state reachable within a documented bound.
- Reuse one invariant implementation for generated and exhaustive checks.
- Reject any transition that promotes without host success or bypasses remount recovery.
- Preserve all reviewed fixtures and deterministic campaign digests.

### Delivered

- Added breadth-first exploration through eight actions of history.
- Covered three `begin_apply` variants plus every other closed action from each reachable state.
- Merged equivalent states at equal depth while retaining every outgoing state/action pair.
- Extracted promotion, revision and recovery invariants into a focused shared module.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Exhaustive bounded transitions | Passed | 567 state/action pairs through depth eight |
| Reachable state coverage | Passed | 19 unique values across all four state types |
| Action coverage | Passed | All seven actions; valid, stale and invalid-revision apply variants |
| Promotion safety | Passed | 16 reachable promotions, each caused only by `host_applied` |
| Recovery safety | Passed | Failed state never reaches ready without successful remount |
| Reproducibility | Passed | SHA-256 `c34965bbb75e3d27d9a78b7a5226650a7e009637e3600edb7075bec6124e4b0d` |
| Regression suite | Passed | Twenty-two Python tests; prior digests unchanged |
| Rust implementation | Deferred | Cargo remains unavailable, so compiled gates cannot run |

The evidence is a bounded proof over the closed executable model, not an unbounded model-checking
claim. Canonical compact JSON with sorted keys makes its traversal digest reproducible according
to the Python standard library's serialization contract.

### Next increment

Specify surface creation, disposal and handle-generation semantics so stale platform callbacks
cannot target a destroyed or newly reused surface before the Android boundary is introduced.

## 2026-09-20 — Generational surface lifecycle contract

### Acceptance criteria

- Make surface creation, callback routing and disposal explicit and closed.
- Prevent a delayed callback or disposal from targeting a recreated logical surface.
- Avoid raw native or Rust pointers as cross-language lifetime identities.
- Represent generation exhaustion without wraparound, panic or silent reuse.

### Delivered

- Accepted ADR-0005 for runtime-owned lifecycle registry semantics.
- Defined positive `(surface_id, generation)` handles with process-wide monotonic generations.
- Added explicit available/exhausted allocator states and typed rejection outcomes.
- Added six exact fixtures and four boundary-focused regression tests.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Lifecycle fixtures | Passed | Six exact creation, callback, disposal and exhaustion scenarios |
| Stale callback isolation | Passed | Prior generation rejected after logical-slot recreation |
| Stale disposal isolation | Passed | Old handle cannot destroy or alter its replacement |
| Surface isolation | Passed | Disposal of one surface leaves another active and routable |
| Exhaustion safety | Passed | Maximum generation allocated once, then creation fails closed |
| Regression suite | Passed | Twenty-six Python tests; existing contracts and digests preserved |
| Rust implementation | Deferred | Registry source remains compile-gated while Cargo is unavailable |

Android lifecycle guidance was reviewed on 2026-09-20. The platform adapter will use lifecycle
cleanup hooks, but Android object identity remains outside the runtime contract. The executable
model is a specification aid and does not claim native integration.

### Next increment

Add deterministic generated lifecycle sequences and verify generation non-reuse, stale-handle
rejection and multi-surface isolation across repeated create/dispose cycles.

## 2026-09-20 — Deterministic generated surface lifecycle sequences

### Acceptance criteria

- Exercise repeated create, callback and dispose operations across multiple logical slots.
- Retain historical handles and prove they never regain validity.
- Verify every valid operation changes only its addressed surface.
- Preserve exact reviewed fixtures and all prior deterministic digests.

### Delivered

- Added eight fixed-seed campaigns with one hundred lifecycle actions each.
- Added independent expected-state checks for creation, callback, disposal and rejection.
- Verified global generation monotonicity and lifetime non-reuse within every campaign.
- Added a reduced reproducibility regression over complete metrics and digest.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Generated actions | Passed | 800 transitions across eight logical surface slots |
| Generation safety | Passed | 148 strictly increasing handles, none reused |
| Disposal coverage | Passed | 112 exact-handle destructions |
| Stale-handle isolation | Passed | 224 rejected callback/disposal attempts with unchanged state |
| Duplicate isolation | Passed | 196 duplicate creates rejected without consuming generations |
| Multi-surface coverage | Passed | Peak of six simultaneously active surfaces |
| Reproducibility | Passed | SHA-256 `efb307a3825a802f684f79581b90ea49bb501011b32fad5968809471e8b15199` |
| Regression suite | Passed | Twenty-seven Python tests; prior evidence unchanged |
| Rust implementation | Deferred | Lifecycle registry remains compile-gated while Cargo is unavailable |

The sampler uses only the Python standard generator's documented compatible `random()` sequence;
bounded selection remains owned by the test harness. These results do not claim concurrency or
Android end-to-end coverage.

### Next increment

Add bounded exhaustive lifecycle exploration over a small surface/generation domain and verify
that every reachable state preserves allocator monotonicity, exact-handle routing and isolation.

## 2026-09-20 — Bounded exhaustive surface lifecycle exploration

### Acceptance criteria

- Enumerate every action from every reachable state in a documented finite lifecycle domain.
- Cover current, stale and never-issued handles for callback and disposal operations.
- Share one transition-invariant implementation with the generated campaign.
- Preserve reviewed fixtures and all prior deterministic digests.

### Delivered

- Added breadth-first exploration through six actions of history.
- Applied eighteen actions per state over two logical slots and four handle generations.
- Extracted allocator, routing and isolation invariants into a focused shared module.
- Added reproducibility and domain-coverage regression assertions.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Exhaustive bounded transitions | Passed | 1,008 state/action pairs through depth six |
| Reachable registry coverage | Passed | 28 unique states; one, two and zero active surfaces |
| Handle-domain coverage | Passed | Callback and disposal for 16 `(surface, generation)` values per state |
| Accepted operation coverage | Passed | 52 creations, 60 disposals and 60 callbacks |
| Stale/future isolation | Passed | 776 exact rejections with unchanged registry state |
| Duplicate isolation | Passed | 60 duplicate creates rejected without allocator movement |
| Reproducibility | Passed | SHA-256 `112e52fc3fad0111ae10813216020f3da0817c955b9407552ae8859cd603266a` |
| Regression suite | Passed | Twenty-eight Python tests; prior evidence unchanged |
| Rust implementation | Deferred | Lifecycle registry remains compile-gated while Cargo is unavailable |

The traversal uses canonical compact JSON with sorted keys for stable state identity and digest.
The result is exhaustive only for the stated depth and finite handle domain; allocator exhaustion
continues to be covered separately by its reviewed boundary fixture.

### Next increment

Specify the Android FFI boundary, including ABI-safe value representation, ownership, threading,
panic containment, error mapping and lifecycle-handle validation before adding JNI source.

## 2026-09-20 — Android JNI boundary v1 contract

### Acceptance criteria

- Freeze a minimal versioned JNI signature without exposing pointers or platform objects.
- Define cross-language ownership, transport ranges, threading and pending-exception behavior.
- Prevent panics and foreign unwinds from crossing the native boundary by contract.
- Make input admission and response framing executable without claiming native integration.

### Delivered

- Accepted ADR-0006 with one `RegisterNatives` entry point and explicit unsafe containment rules.
- Added a closed machine-readable registry for four operations and seven stable status codes.
- Defined positive signed-63-bit transport identifiers and complete generational handles.
- Defined copy-in/copy-out payload ownership with a 1 MiB limit and no global references.
- Fixed a 32-byte little-endian response header with reserved bytes for compatible evolution.
- Added eight reviewed fixtures and a dependency-free admission/response encoder specification.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| FFI admission fixtures | Passed | Eight exact accepted/rejected boundary scenarios |
| ABI drift protection | Passed | Descriptor, operation, status, range and frame registries validated closed |
| Handle transport | Passed | Zero generation allowed only for create; all routed handles are complete |
| Thread boundary | Passed | Off-main input rejected before runtime routing |
| Payload ownership limits | Passed | Exact 1 MiB accepted; one byte beyond rejected |
| Response framing | Passed | Exact 32-byte golden header and registered-status enforcement |
| Regression suite | Passed | Thirty-seven Python tests; every prior contract preserved |
| Native implementation | Deferred | Cargo, Kotlin tooling and Android SDK are unavailable |

Android JNI and Rust FFI documentation were reviewed on 2026-09-20. The executable Python model
checks the language-independent contract only; it does not simulate ART references, Java
exceptions, `catch_unwind`, CheckJNI or an emulator.

### Next increment

Add corruption-oriented response-frame and operation-payload conformance fixtures covering
truncation, reserved bytes, inconsistent lengths and unknown payload versions before JNI source.

## 2026-09-20 — Android FFI binary-frame hardening

### Acceptance criteria

- Decode the complete response frame without trusting its declared length for allocation.
- Bind every non-empty operation payload to its version and JNI operation discriminator.
- Reject truncation, unknown magic/version/status, nonzero reserved bytes and length mismatch.
- Preserve the previously reviewed admission behavior and every earlier contract digest.

### Delivered

- Added focused response and operation-payload codecs separate from request admission.
- Added the `RMP1` 16-byte payload header with version, operation, body length and reserved bytes.
- Integrated payload-frame validation into event and commit-result admission.
- Added reviewed response and payload corpora containing valid and deliberately corrupt frames.
- Added exact round-trip, cross-operation and corpus-completeness regression tests.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Response-frame corpus | Passed | Ten cases including eight malformed or incompatible frames |
| Operation-payload corpus | Passed | Nine cases including seven malformed or mismatched frames |
| Complete-frame validation | Passed | Trailing, missing or inconsistent bytes fail closed |
| Reserved-byte policy | Passed | Nonzero response and payload reserved regions rejected |
| Operation binding | Passed | Event payload cannot be decoded as a commit result |
| Payload budget | Passed | Header plus body accepted at exactly 1 MiB; excess rejected |
| Regression suite | Passed | Forty-one Python tests; prior contracts and digests preserved |
| Native implementation | Deferred | Cargo, Kotlin tooling and Android SDK remain unavailable |

The byte order is explicitly little-endian rather than relying on the default order of a platform
buffer. Android `ByteBuffer` and JNI guidance were reviewed on 2026-09-20. These checks validate
owned bytes only and do not claim JNI, CheckJNI or emulator execution.

### Next increment

Define typed v1 bodies for event dispatch and commit results, including node identity, event code,
revision/outcome fields and strict size limits, before implementing either side of JNI.

## 2026-09-20 — Typed Android FFI operation bodies

### Acceptance criteria

- Give event and commit-result operations fixed, closed, version-one body schemas.
- Reject unknown identities, discriminants, flags, revisions and semantic combinations.
- Integrate typed decoding into admission without weakening the independent frame checks.
- Preserve every earlier contract result and deterministic digest.

### Delivered

- Added a 24-byte event body with positive node identity, registered event code and sequence.
- Registered only `CLICK`; no broader event or React Native compatibility is claimed.
- Added a 24-byte commit-result body with consecutive revisions and closed outcome/reason pairs.
- Added focused, dependency-free typed codecs and a separate machine-readable body corpus.
- Extended admission with one valid commit fixture and one unknown-event rejection fixture.
- Split manifest validation from request admission to keep each checker cohesive.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Admission fixtures | Passed | Ten exact accepted/rejected requests with typed normalized bodies |
| Typed-body corpus | Passed | Fifteen cases; four valid classifications and eleven boundary rejections |
| Binary frame corpus | Passed | Nineteen outer-frame cases remain unchanged |
| Semantic closure | Passed | Unknown events/outcomes/reasons, bad revisions and nonzero evolution fields rejected |
| Regression suite | Passed | Forty-five Python tests; 60 JSON and nine TOML files validated |
| Native implementation | Deferred | Cargo, Kotlin tooling, Gradle and Android SDK remain unavailable |

Android click-listener and UI-thread guidance were reviewed on 2026-09-20. This contract defines
owned bytes and safe normalized values only; it does not claim a listener, JNI registration,
CheckJNI execution or emulator behavior.

### Next increment

Add deterministic byte-level mutation coverage over valid FFI packets so single-field header and
body corruptions must either reject with a registered code or decode as another explicitly valid
message.

## 2026-09-20 — Exhaustive Android FFI single-bit mutation campaign

### Acceptance criteria

- Mutate every bit of representative canonical response, event and commit-result packets.
- Require every rejection to use a registered v1 decoder error.
- Require every accepted mutation to re-encode to exactly the same canonical bytes.
- Produce stable aggregate evidence and preserve all prior contract digests.

### Delivered

- Added a closed campaign registry with seven canonical packets and all eight bit masks.
- Added a dependency-free checker that exhaustively evaluates 2,128 distinct mutations.
- Verified both valid commit failure reasons, safe rejection, success, click and response framing.
- Added canonical re-encoding as an acceptance condition for every surviving mutation.
- Added regression checks for the campaign digest and reachable decoder-error coverage.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| One-bit mutations | Passed | 2,128 mutations across seven canonical packets |
| Rejections | Passed | 1,857 fail closed using 21 registered decoder errors |
| Canonical survivors | Passed | 271 accepted packets re-encode byte-for-byte |
| Decoder registry coverage | Passed | Every bit-reachable error covered; four length-only errors remain in reviewed corpora |
| Reproducibility | Passed | SHA-256 `9e31a82ad3bb38bf8aa8881b9428a6292eacd7ea5b8ad5aba93ecbac8b7da37b` |
| Regression suite | Passed | Forty-seven Python tests; 61 JSON and nine TOML files validated |
| Native implementation | Deferred | Cargo, Kotlin tooling, Gradle and Android SDK remain unavailable |

SHA-256 is used only as a reproducibility fingerprint over canonical JSON records. Python hashing
and Android JNI guidance were reviewed on 2026-09-20. The campaign is exhaustive for one-bit
changes to its seven seeds, not for arbitrary packet lengths or multi-bit corruption.

### Next increment

Define the minimal Android adapter module and Kotlin facade boundaries, source ownership and build
topology without adding JNI implementation while the compiled Rust and Android gates are absent.

## 2026-09-20 — Android module and build topology

### Acceptance criteria

- Assign one owner to JNI safety, public Kotlin API, native view hosting and sample composition.
- Keep domain and runtime independent from Android while allowing the adapter to depend inward.
- Pin the first Android build baseline and supported ABI/Rust-target mapping.
- Reject module cycles, extra exports, publication drift and generated binaries treated as source.

### Delivered

- Accepted ADR-0007 for one internal Rust `cdylib`, one public Android AAR and one sample app.
- Added a closed topology manifest for module ownership, dependencies, visibility and symbols.
- Pinned AGP 9.4.0, Gradle 9.6.0, JDK 17, NDK 28.2.13676358 and SDK 37.
- Limited the initial target set to `arm64-v8a` and `x86_64`, with explicit Rust triples.
- Defined Cargo build followed by generated `jniLibs` staging; no CMake wrapper or tracked `.so`.
- Added an automatic topology checker integrated into the main architecture control.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Android topology | Passed | Three roles, one published module and an acyclic dependency graph |
| Toolchain drift | Passed | Exact versions and SDK/ABI mapping fail closed |
| Native export surface | Passed | Only `JNI_OnLoad` accepted |
| Dependency direction | Passed | JNI may depend only on `rmf-runtime`; domain remains platform-free |
| Regression suite | Passed | Fifty-two Python tests; 62 JSON and nine TOML files validated |
| Compiled Android build | Deferred | Cargo, Kotlin, Gradle, ADB and Android SDK are unavailable |

Android Gradle Plugin 9.4 documentation, native build integration, ABI guidance and JDK guidance
were reviewed on 2026-09-20. The manifest is a verified design contract, not an assembled AAR or
working JNI adapter.

### Next increment

Specify the public Kotlin surface lifecycle facade as an executable state contract, including
main-thread dispatch, idempotent close and stale callback handling, before adding Kotlin source.

## 2026-09-20 — Executable Android Kotlin facade lifecycle

### Acceptance criteria

- Marshal public create and close requests from worker threads without native UI work off main.
- Make close idempotent and issue native disposal at most once for a complete current handle.
- Define both orders of create/close queue and native-result races without surface resurrection.
- Drop callbacks with stale handles, replayed sequences or any state after close is requested.
- Preserve all earlier architecture, reconciliation, runtime lifecycle and FFI contracts.

### Delivered

- Accepted ADR-0008 for the future public `RmfSurfaceHost` lifecycle and ownership boundary.
- Added a closed nine-state model with typed actions, effects, errors and thread policies.
- Added twelve reviewed scenarios for main and worker creation, idempotent close, cancellation,
  both race orders, failures, stale callbacks, thread rejection and handle bounds.
- Limited identities and sequences to the positive Kotlin `Long` range.
- Added strict registry drift checks and five focused regression tests.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Facade scenarios | Passed | Twelve exact state/effect comparisons |
| Worker dispatch | Passed | Create and close post once; repeated close produces no extra task |
| Race safety | Passed | Queued-create-first and native-result-first orders both end closed |
| Callback safety | Passed | Stale handle, replay and post-close callback cases drop deterministically |
| Regression suite | Passed | 57 Python tests, up from 52; all earlier contracts and digests preserved |
| Metadata and architecture | Passed | 75 JSON, nine TOML, links, syntax and both architecture checks |
| Compiled Android build | Deferred | Cargo, Kotlin, Gradle, ADB and Android SDK are unavailable; JDK 17 alone is insufficient |

Android UI-thread, `Handler` and lifecycle guidance were reviewed on 2026-09-20. The model checks
observable orchestration only; it does not claim real Looper ordering, lifecycle-owner behavior,
JNI execution, AAR assembly or device coverage. No dependency or critical debt was added.

### Next increment

Add bounded exhaustive exploration of facade state/action interleavings and reuse shared safety
invariants before translating the contract into compile-gated Kotlin source.

## 2026-09-20 — Bounded exhaustive Android facade exploration

### Acceptance criteria

- Explore every registered facade action from every state reachable in a bounded finite domain.
- Cover all nine states, nine effects and four errors without accepting an unknown outcome.
- Prove within the bound that rejected actions are atomic, native calls remain on main, create and
  dispose occur at most once, terminal states remain terminal and post-close callbacks never pass.
- Make the state and transition invariants reusable outside fixture execution.
- Preserve all reviewed facade scenarios and every earlier contract digest.

### Delivered

- Added a separate facade invariant module for state shape, ownership and transition safety.
- Added a deterministic breadth-first explorer over 32 canonical actions and seven steps.
- Retained path facts for native create/dispose cardinality and whether close was requested.
- Added a canonical SHA-256 digest over every checked transition and three focused regressions.
- Documented the exact finite domain and avoided presenting the result as a formal unbounded proof.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Exhaustive bounded transitions | Passed | 4,832 state/action pairs over 39 unique nodes |
| State coverage | Passed | All nine registered states reached by depth five |
| Effect and error coverage | Passed | All nine effects and four errors observed |
| Safety invariants | Passed | Atomic rejection, main-thread native work, one create/dispose and terminality |
| Reproducibility | Passed | SHA-256 `1b1a683bac60140fabeb301fb714cb0f18b456e969f592f9932f61ff59540495` |
| Regression suite | Passed | 60 Python tests, up from 57; twelve reviewed scenarios unchanged |
| Prior contracts | Passed | Reconciliation, commit, surface lifecycle, FFI and topology evidence preserved |
| Compiled Android build | Deferred | Cargo, Kotlin, Gradle, ADB and Android SDK remain unavailable |

Android's [process and thread guidance](https://developer.android.com/guide/components/processes-and-threads),
last updated 2026-08-28, was rechecked on 2026-09-20. It continues to require UI access on the
main thread and thread-safe handling for methods called from multiple threads, matching the model.
The exploration is exhaustive only for its documented handles, sequences, actions and depth.

### Next increment

Specify a closed, machine-checked public Kotlin API surface and compatibility policy before adding
source that cannot yet pass Kotlin, Gradle, lint or Android compilation gates.

## 2026-09-20 — Public Android Kotlin API design contract

### Acceptance criteria

- Define the complete initial Kotlin source and JVM signature surface without leaking JNI details.
- Keep one cohesive public type with explicit visibility, nullability, threading and ownership.
- Establish binary, source and behavioral compatibility policies plus semantic-versioning rules.
- Require strict API declarations, KDoc, warnings as errors and compiled ABI validation.
- Cross-check public symbols against the Android module topology and reject accidental expansion.

### Delivered

- Accepted ADR-0009 and a closed `0.1.0` public API manifest.
- Limited the AAR to final `RmfSurfaceHost`, a public `ViewGroup` constructor and `close()`.
- Rejected a companion factory during review because it would emit additional public JVM symbols.
- Forbid raw payload bytes, byte buffers, bridge types, pointers and partial surface handles.
- Defined additive-only patches, controlled pre-1.0 breaking minors and major-only stable breaks.
- Added a dependency-free checker and nine regressions for declarations, descriptors, forbidden
  types, close semantics, build policy and topology ownership.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Public declaration registry | Passed | One final class and two exact JVM descriptors |
| Boundary leakage | Passed | JNI bytes, native pointers, bridge types and handles forbidden |
| Compatibility policy | Passed | Binary required; source best effort; behavior bound to executable contracts |
| Android ownership | Passed | Manifest symbols exactly match the published framework module |
| Regression suite | Passed | 69 Python tests, up from 60; all earlier contracts preserved |
| Metadata and architecture | Passed | 76 JSON, nine TOML, links, syntax and architecture checks |
| Compiled ABI evidence | Deferred | Kotlin, Gradle and Android SDK are unavailable; descriptors remain design expectations |

The official Kotlin [backward-compatibility guidance](https://kotlinlang.org/docs/api-guidelines-backward-compatibility.html)
dated 2026-07-15 and [ABI validation documentation](https://kotlinlang.org/docs/gradle-binary-compatibility-validation.html)
dated 2026-04-28 were reviewed on 2026-09-20. Android's built-in Kotlin guidance, updated
2026-09-15, confirms that [AGP 9 enables Kotlin by default](https://developer.android.com/build/migrate-to-built-in-kotlin),
so the separate Android Kotlin plugin is intentionally forbidden. No dependency or critical debt
was added.

### Next increment

Specify executable Android container ownership and detach semantics—single host per `ViewGroup`,
close cleanup and stale mount rejection—before adding an uncompiled Kotlin view host.

## 2026-09-20 — Android container ownership contract

### Acceptance criteria

- Allow at most one current framework host per application-provided container.
- Reject duplicate claims and roots that already belong to another active or retired mount.
- Cancel a reserved attachment or remove exactly the owned root when close wins.
- Make repeated release harmless and prevent stale results from changing a replacement host.
- Keep hierarchy effects on the main thread and all identities inside positive Kotlin `Long`.

### Delivered

- Accepted ADR-0010 and a closed v1 container contract below the public Kotlin facade.
- Added a dependency-free state model for reserved and attached bindings with monotonic mount IDs.
- Added eleven reviewed scenarios covering 32 actions, all seven effects and four observed errors.
- Made rejection atomic, release idempotent and exact-root cleanup explicit; `removeAllViews` is not
  part of the contract because application-owned siblings remain outside framework ownership.
- Added six regressions for the corpus, duplicate ownership, ID exhaustion, stale-root isolation,
  boolean identity rejection and closed vocabulary.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Exclusive ownership | Passed | Duplicate host on the same container is rejected atomically |
| Detach semantics | Passed | Reserved mounts cancel; attached mounts remove one exact root |
| Replacement isolation | Passed | Old results cannot release or remove the new host's active root |
| Identity safety | Passed | Positive monotonic mount IDs; exhaustion rejects without wraparound |
| Threading | Passed | Every accepted hierarchy operation requires the main thread |
| Regression suite | Passed | 75 Python tests, up from 69; all earlier contracts preserved |
| Metadata and architecture | Passed | 78 JSON, nine TOML, links, syntax and architecture checks |
| Android execution | Deferred | Kotlin, Gradle, ADB and Android SDK remain unavailable |

Android's [`ViewGroup`](https://developer.android.com/reference/android/view/ViewGroup) reference,
last updated 2026-08-28, was reviewed on 2026-09-20. Its exact-child `addView` and `removeView`
operations and parent relationship support the contract, but no Android call is claimed executed.
No dependency or critical debt was added.

### Next increment

Add bounded exhaustive exploration of container claim, attach, release and replacement
interleavings before translating the contract into Kotlin source that cannot yet compile here.

## 2026-09-21 — Bounded exhaustive Android container exploration

### Acceptance criteria

- Explore every canonical claim, attach result, failure and release from every reachable state.
- Cover both binding states, all seven effects and all five registered errors.
- Check atomic rejection, exclusive root ownership, monotonic mount allocation and exact cleanup.
- Include allocator exhaustion without requiring billions of transitions to reach the boundary.
- Produce a deterministic digest and preserve all earlier contract evidence.

### Delivered

- Extracted container state and transition invariants into a reusable module.
- Reused the same invariants from reviewed fixtures and bounded breadth-first exploration.
- Explored 54 actions across two containers, two hosts, three mount IDs and two root identities.
- Seeded normal and exhausted allocator states, then explored five steps without ID wraparound.
- Added regressions for deterministic reproduction and duplicate-root invariant detection.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Bounded transitions | Passed | 19,926 state/action pairs over 347 unique states |
| State coverage | Passed | `RESERVED` and `ATTACHED` both reached |
| Outcome coverage | Passed | All seven effects and five errors observed |
| Ownership invariants | Passed | One binding per container and one owner per active root |
| Boundary safety | Passed | Exhaustion, invalid IDs and worker-thread operations reject atomically |
| Reproducibility | Passed | SHA-256 `819baa584e22e9dcf0a0645046332ab2bd0de00345030546f7e85d22c884beda` |
| Regression suite | Passed | 77 Python tests, up from 75; prior contract digests unchanged |
| Metadata and architecture | Passed | 78 JSON, nine TOML, links, syntax and architecture checks |
| Android execution | Deferred | Kotlin, Gradle, ADB and Android SDK remain unavailable |

Android's [`ViewGroup`](https://developer.android.com/reference/android/view/ViewGroup) and
[process/thread guidance](https://developer.android.com/guide/components/processes-and-threads)
were rechecked on 2026-09-21. The bounded model preserves exact-child cleanup and main-thread UI
work but does not claim a formal proof or executed Android hierarchy. No dependency or critical
debt was added.

### Next increment

Define and execute the composition contract joining facade lifecycle, container ownership and
generational surface lifecycle before introducing Kotlin/JNI source that cannot compile here.

## 2026-09-21 — Android host composition contract

### Acceptance criteria

- Attach the exact owned root before requesting native surface creation.
- Guarantee that `ACTIVE` has both a live generational surface and attached root.
- Clean up the host's root and surface on failure, close and late-create races.
- Reject stale callbacks before facade delivery and preserve foreign/replacement resources.
- Reuse the existing lifecycle contracts without duplicating their domain rules.

### Delivered

- Accepted ADR-0011 and added a main-thread composition model over the facade, container and
  surface contracts.
- Extracted surface transitions from fixture I/O into a reusable dependency-free model.
- Added seven reviewed scenarios covering normal activation, callback delivery, both close paths,
  native failure, stale generations, repeated close and wrong-thread rejection.
- Added targeted regressions for foreign container, root and surface ownership, invalid identity,
  callback gate ordering, out-of-range generations and invalid transition atomicity.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Reviewed composition | Passed | Seven scenarios, 21 actions and all nine outcome classes |
| Activation ordering | Passed | Native creation is requested only after exact-root attachment |
| Failure cleanup | Passed | Native failure releases root; collisions preserve foreign resources |
| Close race | Passed | Late successful create is immediately disposed after root release |
| Callback admission | Passed | Stale generation cannot advance facade sequence state |
| Regression suite | Passed | 85 Python tests, up from 77; all earlier contracts preserved |
| Android execution | Deferred | Kotlin, Gradle, ADB and Android SDK remain unavailable |

Android's main-thread rules and JNI boundary guidance were rechecked on 2026-09-21. This is an
executable orchestration contract, not evidence of compiled JNI, `ViewGroup` calls or device
execution. No dependency or critical debt was added.

### Next increment

Add bounded exhaustive exploration of composed start, native result, callback and close
interleavings before translating the contract into Kotlin/JNI source.

## 2026-09-21 — Rust generational surface registry

### Acceptance criteria

- Replace the surface-lifecycle specification gap with safe production Rust in `rmf-runtime`.
- Make zero identities, duplicate logical slots, stale generations and allocator exhaustion
  explicit typed failures without panic or `unsafe`.
- Preserve the independent contract evidence while making Rust CI mandatory before `main`.
- Verify formatting, Clippy, tests, rustdoc, architecture and the release benchmark remotely.

### Delivered

- Added `SurfaceId`, opaque monotonic generations, complete handles and a serialized registry.
- Added exact-handle callback admission and disposal, logical-slot reuse isolation and explicit
  `u64` exhaustion without generation wraparound.
- Added six Rust unit tests, including compile-time `Send + Sync` checks.
- Added a pinned GitHub Actions gate because the local execution image has no Rust toolchain.

### Validation evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Rust formatting | Passed | Rust 1.85.0 `cargo fmt --all --check` in GitHub Actions |
| Rust linting | Passed | Strict workspace Clippy with all targets/features and `-D warnings` |
| Rust tests | Passed | 13 tests: four core, seven runtime and two headless-adapter tests |
| Rust documentation | Passed | Workspace rustdoc with `-D warnings` and no dependencies |
| Independent regressions | Passed | Architecture check and all 85 Python tests |
| Release performance gate | Passed | 1,000 nodes × 100 iterations; all three budgets passed |

The validated run measured 50,141 ns average tree validation, 104,980 ns average headless mount
and a 1,007,899-byte frame. The result is recorded in
[GitHub Actions run 35567268665](https://github.com/nikorasu96/rust-mobile-framework/actions/runs/35567268665).
Python remains independent test support and is not the production implementation. Android,
Kotlin, Gradle, ADB and the Android SDK remain unavailable, so this increment makes no Android
execution claim.

### Next increment

Move a first reviewed surface-lifecycle fixture into a Rust integration contract test while
extending the Rust runtime orchestration through a narrow use-case API.

## 2026-09-21 — Runtime surface orchestration in Rust

### Acceptance criteria

- Make the runtime own the surface registry instead of requiring callers to compose it manually.
- Route creation, exact-handle disposal and callback admission through explicit Rust use cases.
- Guarantee that rejected callbacks cannot execute user code.
- Translate reviewed lifecycle scenarios into integration tests against the public Rust API.

### Delivered

- Extended `Runtime<R>` with typed surface creation, disposal and callback dispatch operations.
- Kept rendering behind the existing small `Renderer` port and surface state inside the runtime.
- Used a one-shot callback so admission is checked immediately before a single invocation.
- Added two integration tests reproducing create/callback/dispose, duplicate creation and stale
  callback rejection after logical-slot replacement.

### Validation evidence

The final Rust test count, CI run, commit SHA and benchmark measurements are recorded after the
branch passes formatting, strict Clippy, tests, rustdoc, architecture checks and release budgets.
Python remains independent regression evidence and no new Python model was added.

Rust's current [`FnOnce` documentation](https://doc.rust-lang.org/std/ops/trait.FnOnce.html) was
reviewed on 2026-09-21. It matches this boundary because an admitted callback is invoked no more
than once while still allowing callers to consume captured state.
