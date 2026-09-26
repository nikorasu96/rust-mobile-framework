# ADR-0012: Remove caller-identified bootstrap rendering

- Status: Accepted
- Date: 2026-09-26
- Depends on: ADR-0002, ADR-0003 and ADR-0004

## Context

The bootstrap API accepted caller-created `NodeId` values in `rmf-core::UiTree` and replaced a
complete frame through `rmf-runtime::Renderer`. That temporary path contradicted ADR-0002 after
the production reconciler became the authority for identities. Keeping both paths would permit
new adapters to bypass candidate validation, revision guards and apply-then-promote recovery.

The headless example, release benchmark and adapter contracts now exercise the complete
declaration-to-confirmed-host pipeline. The old renderer therefore provides no unique production
evidence and retains TD-003 and TD-005.

## Decision

Version `0.2.0-alpha.1` removes the APIs. Cargo treats a change to the left-most non-zero
component of a `0.y.z` version as incompatible, so moving from `0.1` to `0.2` makes the source
break explicit even though every package remains pre-alpha and unpublished.

- `rmf_core::{NodeId, NodeIdError, Element, UiNode, UiTree, TreeError}`;
- `rmf_runtime::Renderer`, generic `Runtime<R>`, `Runtime::mount` and renderer accessors;
- `rmf_renderer_headless::HeadlessRenderer`.

`Runtime` remains a non-generic owner of surface lifecycle. Tree updates use `ValidatedTree`,
`Reconciler::prepare`, `CommitCoordinator` and a `BatchApplier`/`SnapshotRemounter` adapter.
`rmf-reconciliation::NodeId` remains runtime-owned and cannot be supplied by a frontend.

## Source migration

| Removed API | Replacement |
| --- | --- |
| `UiNode::new` / `UiTree::new` | `DeclarativeNode` followed by `ValidatedTree::new` |
| Caller-created `rmf_core::NodeId` | No public replacement; reconciliation allocates `rmf_reconciliation::NodeId` |
| `Runtime::new(renderer)` | `Runtime::new()` for lifecycle and `CommitCoordinator::new(adapter)` for host commits |
| `Runtime::mount(tree)` | `Reconciler::prepare` followed by `CommitCoordinator::apply` |
| `Runtime::renderer` / `into_renderer` | `CommitCoordinator::applier` / `into_applier` |
| `HeadlessRenderer` | `HeadlessMutationAdapter` |

This is an intentional pre-alpha source break. There is no compatibility shim because a shim
would preserve caller-controlled runtime identity and allow bypassing the committed state machine.

## Consequences

- Core exposes one declarative model and no caller-owned runtime identity.
- Runtime no longer depends on `rmf-core` merely to support obsolete full-tree mounting.
- Every host adapter shares revision, recovery and snapshot-promotion semantics.
- Downstream pre-alpha users must migrate composition roots before upgrading.
- This decision does not imply React Native source or behavioral compatibility.

## References

- [Cargo SemVer compatibility](https://doc.rust-lang.org/cargo/reference/semver.html)
- [Cargo manifest version field](https://doc.rust-lang.org/cargo/reference/manifest.html#the-version-field)
