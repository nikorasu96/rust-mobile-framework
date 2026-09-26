# Technical debt register

| ID | Priority | Item | Exit criterion |
| --- | --- | --- | --- |
| TD-001 | Medium | Rust toolchain unavailable locally; compilation depends on repository CI | Provide a pinned local toolchain or keep every Rust increment gated by successful CI |
| TD-003 | Medium | Full-tree rendering allocates a diagnostic string recursively | Capture a compiled baseline and use profiles before choosing reconciliation or allocation changes |
| TD-004 | Medium | Bootstrap benchmark reports averages only and has no hardware baseline | Add warmup, percentiles and recorded release baseline when Rust execution is available |
| TD-005 | High | Reconciliation owns `NodeId` for initial and stable-tree updates, but the bootstrap runtime still accepts caller-assigned IDs | Add structural reconciliation, integrate `PreparedCommit` into runtime, then remove the bootstrap tree before Android work |
| TD-006 | Medium | Production handles one keyed move, insertion, removal or replacement linearly; general wide reorders still need order maintenance | Select and benchmark a non-quadratic multi-move strategy before general reorder support |

Critical debt: none. High debt blocks the Android implementation until the
declarative/committed split is complete. Rust build claims require successful repository CI
while the local toolchain remains absent.
