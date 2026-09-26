# rmf-reconciliation

Pure core service that assigns runtime node identities and prepares immutable snapshots plus
deterministic host mutation batches. Its only dependency is `rmf-core`; it contains no renderer,
runtime orchestration, Android, JNI or TypeScript concerns.

The current implementation supports initial mounting, property updates and one keyed child move
per sibling list. Single moves are detected with bounded linear scans and preserve all matching
runtime identities. Structural insertion, removal, replacement and reorders requiring multiple
moves are rejected with a typed error until their mutation-ordering strategy is implemented and
benchmarked.

Ownership rules:

- callers borrow the current snapshot and candidate during preparation;
- `PreparedCommit` owns both the batch and unpublished next snapshot;
- committed nodes use parent-to-child `Arc` ownership without parent pointers;
- only `into_snapshot` transfers the prepared state for promotion after host success.
