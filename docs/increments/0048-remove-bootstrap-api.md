# Increment 48: Versioned removal of caller-identified bootstrap APIs

- Date: 2026-09-26
- Status: Pending repository CI

## Acceptance criteria

- Remove caller-owned runtime identities and the obsolete full-tree renderer from production Rust.
- Preserve surface lifecycle and committed host application as separate, narrow responsibilities.
- Publish an explicit source migration and pre-alpha breaking version.
- Retire TD-003 and TD-005 only after all local and repository gates pass.
- Keep Android and React Native compatibility claims unchanged.

## Delivered

- Reduced `rmf-core` to the declarative candidate model; runtime `NodeId` remains reconciler-owned.
- Made `Runtime` a non-generic surface-lifecycle orchestrator with no renderer or mount methods.
- Removed `HeadlessRenderer` while retaining the mutation/remount adapter used by production flows.
- Bumped every workspace package to `0.2.0-alpha.1` and added ADR-0012's migration table.
- Removed the obsolete runtime-to-core dependency and resolved TD-003 and TD-005.

## Validation evidence

Repository CI evidence will be recorded before this increment is merged.

## Next increment

Select and benchmark a non-quadratic general keyed-reorder strategy before expanding structural
reconciliation beyond one change per sibling list.
