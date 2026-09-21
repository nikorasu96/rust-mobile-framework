# ADR-0003: Reconciliation crate boundary and public type contract

- Status: Accepted boundary; implementation blocked by TD-001
- Date: 2026-09-20
- Depends on: ADR-0001 and ADR-0002

## Context

ADR-0002 defines reconciliation behavior, but not which crate owns each type or how the
runtime consumes a prepared commit. Implementing the algorithm before fixing this boundary
would risk leaking mutable trees, caller-assigned identities or Android concerns into the
domain. The executable v1 fixtures now provide enough evidence to freeze a small Rust API.

This decision defines the implementation target. It does not claim that the crate exists or
compiles yet; Rust source is intentionally deferred until the pinned toolchain can execute
formatting, Clippy and tests.

## Decision

### 1. Crate responsibility and dependency direction

```text
rmf-core <- rmf-reconciliation <- rmf-runtime <- adapters/composition roots
```

`rmf-core` owns platform-independent declarative values and validation:

- `ComponentKind`, `Key`, `PropertyId`, `PropertyValue` and `PropertySet`;
- `DeclarativeNode` and the opaque `ValidatedTree` produced only by validation;
- component schemas and candidate-tree defensive limits.

`rmf-reconciliation` owns the pure commit calculation:

- runtime `NodeId` allocation and non-reuse;
- `Revision`, committed snapshots and immutable committed nodes;
- the six-operation mutation vocabulary and immutable batches;
- preparation errors and operation-count limits;
- deterministic matching and ordering, with no host side effects.

`rmf-runtime` owns the use case that applies a batch through a host port and promotes the
prepared snapshot only after successful application. It serializes commits per surface and
maps host failure to surface recovery. Reconciliation does not import runtime traits.

The new crate will initially use `publish = false`, inherit workspace lints and have exactly
one Cargo dependency: the local `rmf-core` package. External dependencies, feature flags,
build scripts, platform conditions and unsafe exceptions require a separate reviewed ADR.

### 2. Normative public type shape

The first implementation must preserve this semantic surface. Rust spelling may change only
to satisfy the compiler or Clippy without weakening an invariant.

```rust
pub struct NodeId(/* private NonZeroU64 */);
pub struct Revision(/* private u64 */);
pub struct ChildIndex(/* private u32 */);

pub struct ReconcileLimits {
    /* private, non-zero maximum operation count */
}

pub struct CommittedNode(/* private Arc-backed immutable representation */);
pub struct SurfaceSnapshot(/* private revision, optional root, next identity */);

pub enum Mutation {
    Create { node_id: NodeId, kind: ComponentKind },
    UpdateProperties {
        node_id: NodeId,
        set: PropertySet,
        remove: Box<[PropertyId]>,
    },
    InsertChild { parent_id: NodeId, child_id: NodeId, index: ChildIndex },
    MoveChild {
        parent_id: NodeId,
        child_id: NodeId,
        from: ChildIndex,
        to: ChildIndex,
    },
    RemoveChild { parent_id: NodeId, child_id: NodeId, index: ChildIndex },
    Delete { node_id: NodeId },
}

pub struct MutationBatch(/* private revisions and boxed operations */);
pub struct PreparedCommit(/* private batch and next snapshot */);
pub struct Reconciler(/* private limits; no mutable surface state */);

pub enum ReconcileError {
    RevisionExhausted,
    IdentityExhausted,
    OperationLimitExceeded { limit: u32 },
    InvariantViolation { code: InvariantCode },
}
```

Required observation methods are narrow and read-only:

- `NodeId::get`, `Revision::get` and `ChildIndex::get` return primitive values;
- committed nodes expose identity, kind, properties and borrowed child iteration;
- snapshots expose revision and optional root by shared reference;
- batches expose base/target revisions and `&[Mutation]`;
- `PreparedCommit::batch(&self)` borrows the batch;
- `PreparedCommit::into_snapshot(self)` consumes the preparation after host success;
- `SurfaceSnapshot::empty()` is the only public initial-state constructor;
- `Reconciler::new(limits)` validates limits and returns `Result`;
- `Reconciler::prepare(&self, current, candidate)` returns `Result<PreparedCommit,
  ReconcileError>` and has no side effects.

No public constructor accepts a raw `NodeId`, committed node, batch operation sequence or
allocator state. This keeps invalid and forged runtime states unrepresentable. A future
snapshot persistence format requires its own validated restoration API and versioned contract.

### 3. Ownership, immutability and threading

- `ValidatedTree` and `SurfaceSnapshot` are borrowed during preparation.
- `PreparedCommit` owns the next snapshot and batch; failure drops both without publication.
- Committed node internals use parent-to-child `Arc` ownership only. Nodes store no strong or
  weak parent pointers, so the representation cannot form ownership cycles.
- Public values contain no `Cell`, `RefCell`, `Mutex`, `RwLock`, raw pointer or platform handle.
- Types are expected to be `Send + Sync` through their members; compile-time assertions test
  this rather than unsafe marker implementations.
- Cloning a snapshot or subtree shares immutable storage. Mutation through shared storage is
  forbidden; construction creates new nodes along changed paths.

### 4. Error and panic contract

Every expected failure returns `ReconcileError`. Production paths contain no `panic!`,
`unwrap` or `expect`. Integer increments and index conversions are checked. Allocation
failure follows Rust's process allocation behavior and is not disguised as a recoverable
domain error.

`InvariantViolation` indicates an internal defect or corrupted trusted snapshot, not invalid
application input. Its stable code may be logged, but tree contents and property values are
not included automatically. Candidate validation errors remain owned by `rmf-core` and occur
before reconciliation.

### 5. ABI and platform boundary

These Rust types have no stable ABI, receive no `repr(C)` promise and never cross JNI. An
Android adapter receives a versioned serialized or explicitly converted platform DTO owned by
the future FFI crate. That boundary must validate lengths, discriminants, threading and errors
before constructing safe adapter commands.

### 6. Extension policy

The reconciler is a concrete stateless service rather than a trait with one implementation.
Extension occurs through validated component schemas and composition at runtime ports. A
reconciliation strategy trait is added only when a second real implementation demonstrates a
substitution requirement and shares the same contract suite.

## Compile-gated acceptance criteria

The crate may enter the workspace only in an increment where all of these run successfully:

1. `cargo fmt --all --check`.
2. `cargo clippy --workspace --all-targets --all-features -- -D warnings`.
3. `cargo test --workspace --all-targets --all-features`.
4. Rust contract tests translated from all reconciliation v1 golden fixtures.
5. Generated invariant campaigns compared with the independent host model.
6. Compile-time `Send + Sync` assertions for public immutable values.
7. Rustdoc with `-D warnings` and examples for every public type.
8. Architecture verification proving only `rmf-core` is depended on by the new crate.
9. Dependency license and vulnerability checks, even if the expected dependency set is local.

Until those gates pass, roadmap status remains “executable contract,” not “Rust
implementation.” JNI and Android work remain blocked by TD-001 and TD-005.

## Consequences

- The domain stays independent from runtime, Android, TypeScript and renderers.
- The runtime can enforce apply-then-promote without giving adapters tree ownership.
- Runtime identities and committed states cannot be forged through normal public APIs.
- Structural sharing is possible without shared mutation or reference cycles.
- An extra crate boundary is justified by distinct ownership and contract-testable behavior.
- Persistence, wire encoding and alternative algorithms are deliberately deferred.

## References

- [Rust `NonZeroU64`](https://doc.rust-lang.org/std/num/type.NonZeroU64.html)
- [Rust `Arc`](https://doc.rust-lang.org/std/sync/struct.Arc.html)
- [Cargo package publication control](https://doc.rust-lang.org/cargo/reference/manifest.html#the-publish-field)
- [Cargo workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html)
