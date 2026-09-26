# Increment 48: Versioned removal of caller-identified bootstrap APIs

- Date: 2026-09-26
- Status: Validated in repository CI

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

| Check | Result | Evidence |
| --- | --- | --- |
| Rust formatting and linting | Passed | Rust 1.85.0 fmt and strict Clippy with all targets/features |
| Rust tests | Passed | 51 workspace tests after removal of seven obsolete bootstrap tests |
| Rust documentation | Passed | Workspace rustdoc with warnings denied |
| Dependency and architecture policy | Passed | Runtime production dependency removed; inward-only test dependency retained |
| Independent regressions | Passed | Architecture check and all 85 Python specification tests |
| Release performance gate | Passed | Candidate, committed mount and existing reconciliation/commit budgets |

[GitHub Actions run 36278382712](https://github.com/nikorasu96/rust-mobile-framework/actions/runs/36278382712)
measured 113,880 ns average candidate validation and 350,799 ns average initial reconciliation,
atomic host application and promotion for 1,001 nodes. Existing averages remained within budget:
114,279 ns movement, 105,356 ns insertion, 104,506 ns removal, 103,612 ns replacement and
106,518 ns unchanged commit promotion. These release-runner averages are not tail-latency claims.
Python remains independent verification and contains no runtime implementation.

## Next increment

Select and benchmark a non-quadratic general keyed-reorder strategy before expanding structural
reconciliation beyond one change per sibling list.
