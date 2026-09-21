# ADR-0002: Immutable properties and deterministic reconciliation

- Status: Accepted for implementation after the Rust build gate passes
- Date: 2026-09-19
- Supersedes: the bootstrap assumption that callers assign every `NodeId`

## Context

The bootstrap runtime mounts a complete validated tree. Updates need stable identity,
typed properties and a deterministic mutation protocol before Android host views can be
introduced. Designing this boundary after JNI would couple core semantics to Android.

React Native's documented pipeline separates render, commit and mount, uses immutable
shadow trees with structural sharing, and turns tree differences into host mutations.
React also documents that type, tree position and keys affect preservation of state.
These are useful architectural constraints, but this framework defines its own public
types and does not claim internal or drop-in compatibility.

## Decision

### 1. Immutable committed trees

A committed `UiTree` is immutable and identified by a monotonically increasing
`Revision`. Updates construct a candidate tree. A successful commit atomically publishes
the candidate as the next logical tree; readers never observe a partially built tree.

Nodes use structural sharing (`Arc`-backed internals) after the bootstrap API is migrated.
Unchanged subtrees can therefore be shared across revisions. Mutation through shared
references is forbidden; platform-local state is not stored in the declarative tree.

### 2. Public keys versus runtime identities

- `Key` is an optional public, opaque UTF-8 value scoped to siblings.
- `NodeId` is an internal runtime identity allocated by the reconciler.
- IDs are monotonically allocated and never reused during a surface lifetime.
- Duplicate keys among siblings make the candidate tree invalid.
- A keyed child matches only the same key and component kind under the same parent.
- An unkeyed child matches by sibling position and component kind.
- A changed key or component kind replaces the node and resets its host-local state.

Applications must not serialize, persist, calculate with, or supply `NodeId` values.
The TypeScript facade may expose keys but never runtime IDs.

### 3. Closed, typed property values

Every host component has a versioned property schema. Schema generation assigns a
`PropertyId(u32)` and component kind; string property names never cross the hot FFI path.

The initial closed `PropertyValue` family will support:

- booleans and signed 64-bit integers;
- finite canonical `f64` values (NaN and infinity are rejected);
- immutable UTF-8 strings with explicit byte limits;
- semantic colors, dimensions and accessibility values as dedicated types;
- `EventHandlerId` tokens, separate from executable callbacks.

Arbitrary JSON, platform objects, raw pointers and executable closures are forbidden.
A `PropertySet` is immutable, sorted by `PropertyId`, and contains each property at most
once. Equality is deterministic; order supplied by a caller has no semantic effect.
Unknown or invalid properties fail validation before diffing.

### 4. Reconciliation result

The reconciler is a pure core service:

```text
reconcile(previous committed tree, validated candidate tree)
    -> MutationBatch(base_revision, target_revision, operations)
```

The initial operation vocabulary is deliberately small:

| Operation | Meaning |
| --- | --- |
| `Create` | Allocate a host representation for a new runtime node |
| `UpdateProperties` | Apply a typed property delta to an existing node |
| `InsertChild` | Attach a created or moved child at an index |
| `MoveChild` | Reorder an existing child under the same parent |
| `RemoveChild` | Detach a child from its parent |
| `Delete` | Release a detached host representation |

Cross-parent movement is represented as remove plus insert. Reparenting must preserve an
identity only when the component contract explicitly allows it; the initial contract
does not, so reparenting replaces the node.

### 5. Ordering and application contract

A batch is immutable and topologically ordered:

1. Parents are created before their new descendants are attached.
2. Property initialization occurs after creation and before first attachment.
3. Removals occur before deletion; descendants are deleted before ancestors.
4. No operation references an ID absent from either the base tree or an earlier create.
5. Applying the same batch twice is rejected by its base revision, not silently repeated.

An adapter validates the complete batch and base revision before touching host views.
Logical publication is atomic. Native UI toolkits are not assumed to provide rollback;
if an unexpected host operation fails after validation, the surface enters a failed
state, reports a typed diagnostic, and requires a full remount. Partial success must
never be reported as a committed revision.

### 6. Threading and ownership

- Tree construction, validation, diffing and layout may run away from the UI thread.
- A surface serializes commits using its current revision as an optimistic guard.
- Stale batches are rejected and recalculated against the latest committed tree.
- Mount adapters apply batches only on the host UI thread.
- Event callbacks carry surface revision, node identity and handler token; stale or
  deleted identities are ignored with a trace event rather than dispatched incorrectly.

### 7. Complexity and defensive limits

Keyed sibling matching targets expected `O(n)` time using a temporary index. Unkeyed
matching is linear by position. The first implementation must not contain an accidental
quadratic sibling scan.

Every surface configuration defines limits for node count, depth, children per node,
properties per node, string bytes and total batch operations. Limit violations are typed
validation failures. Recursive algorithms require explicit depth checks; iterative
traversal is preferred for untrusted or deeply nested input.

## Required verification before acceptance

1. Golden tests for create, update, insert, move, remove, delete and replacement.
2. Contract tests proving operation ordering and revision rejection.
3. Property tests: applying a batch to the old model equals the new model.
4. Fuzz tests for duplicate keys, invalid properties, depth and size limits.
5. Tests proving stable identity for matched keyed and unkeyed nodes.
6. Tests proving replacement on key or component-kind change.
7. Determinism tests across repeated runs and hash-map seed variation.
8. Benchmarks for 1k, 10k and wide sibling lists with an explicit no-quadratic gate.

## Migration from the bootstrap model

The pre-alpha `UiNode::new(NodeId, ...)` API is temporary. Migration will introduce a
declarative node without caller-assigned IDs, then place runtime identities in committed
nodes. Because the project is pre-alpha and unpublished, this breaking correction must
happen before a stable facade or Android adapter is built.

## Consequences

- Core semantics remain independent of JavaScript, JNI and host views.
- Typed schemas reduce FFI serialization and reject invalid states early.
- Immutable revisions support concurrent preparation without shared mutation.
- Host failures require explicit surface recovery instead of pretending rollback.
- Structural sharing and keyed reconciliation add complexity that must be justified by
  property tests and benchmarks before optimization claims.

## References

- [React Native: Render, Commit, and Mount](https://reactnative.dev/architecture/render-pipeline)
- [React Native: Fabric](https://reactnative.dev/architecture/fabric-renderer)
- [React: Preserving and Resetting State](https://react.dev/learn/preserving-and-resetting-state)

