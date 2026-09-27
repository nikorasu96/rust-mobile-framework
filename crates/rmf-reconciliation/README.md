# rmf-reconciliation

Pure core service that assigns runtime node identities and prepares immutable snapshots plus
deterministic host mutation batches. Its only dependency is `rmf-core`; it contains no renderer,
runtime orchestration, Android, JNI or TypeScript concerns.

The current implementation supports initial mounting, property updates, arbitrary permutations of
fully keyed compatible siblings, any pure keyed insertion or removal set, and one keyed replacement
per sibling list.
General reorder planning combines expected constant-time key lookup with a Fenwick order-statistics
index, using `O(n log n)` time and `O(n)` memory without depending on hash iteration order. Matching
runtime identities are preserved. Removal detaches every subtree edge before deleting nodes
descendant-first. Replacement always allocates fresh identities for incompatible keyed nodes.
Multiple replacements, mixed structural changes and unkeyed reorders remain typed errors.

Ownership rules:

- callers borrow the current snapshot and candidate during preparation;
- `PreparedCommit` owns both the batch and unpublished next snapshot;
- committed nodes use parent-to-child `Arc` ownership without parent pointers;
- only `into_snapshot` transfers the prepared state for promotion after host success.
