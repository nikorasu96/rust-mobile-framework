# Technical debt register

| ID | Priority | Item | Exit criterion |
| --- | --- | --- | --- |
| TD-001 | Medium | Rust toolchain unavailable locally; compilation depends on repository CI | Provide a pinned local toolchain or keep every Rust increment gated by successful CI |
| TD-003 | Medium | Full-tree rendering allocates a diagnostic string recursively | Capture a compiled baseline and use profiles before choosing reconciliation or allocation changes |
| TD-004 | Medium | Bootstrap benchmark reports averages only and has no hardware baseline | Add warmup, percentiles and recorded release baseline when Rust execution is available |
| TD-005 | High | Bootstrap API lets callers assign `NodeId` and owns mutable-style vectors | Implement the ADR-0003 crate boundary and migrate to the ADR-0002 declarative/committed split before Android or public facade work |
| TD-006 | Medium | Reference mutation ordering uses list index/insert operations for wide reorders | Select and benchmark an order-maintenance strategy before the production Rust reconciler is accepted |

Critical debt: none. High debt blocks the Android implementation until the
declarative/committed split is complete. Rust build claims require successful repository CI
while the local toolchain remains absent.
