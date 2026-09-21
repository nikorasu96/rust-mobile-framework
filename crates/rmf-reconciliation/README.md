# rmf-reconciliation

Pure core service that assigns runtime node identities and prepares immutable snapshots plus
deterministic host mutation batches. Its only dependency is `rmf-core`; it contains no renderer,
runtime orchestration, Android, JNI or TypeScript concerns.

The current implementation supports initial mounting and property-only updates when component
kind, key, sibling position and child count remain stable. Structural insertion, removal,
replacement and reorder are rejected with a typed error until their mutation-ordering strategy is
implemented and benchmarked.

Ownership rules:

- callers borrow the current snapshot and candidate during preparation;
- `PreparedCommit` owns both the batch and unpublished next snapshot;
- committed nodes use parent-to-child `Arc` ownership without parent pointers;
- only `into_snapshot` transfers the prepared state for promotion after host success.
