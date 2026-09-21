# Technical debt register

| ID | Priority | Item | Exit criterion |
| --- | --- | --- | --- |
| TD-001 | High | Rust toolchain unavailable in the initial execution environment | Run format, Clippy, tests, docs and example successfully on pinned Rust 1.85.0 |
| TD-003 | Medium | Full-tree rendering allocates a diagnostic string recursively | Capture a compiled baseline and use profiles before choosing reconciliation or allocation changes |
| TD-004 | Medium | Bootstrap benchmark reports averages only and has no hardware baseline | Add warmup, percentiles and recorded release baseline when Rust execution is available |
| TD-005 | High | Bootstrap API lets callers assign `NodeId` and owns mutable-style vectors | Implement the ADR-0003 crate boundary and migrate to the ADR-0002 declarative/committed split before Android or public facade work |
| TD-006 | Medium | Reference mutation ordering uses list index/insert operations for wide reorders | Select and benchmark an order-maintenance strategy before the production Rust reconciler is accepted |

Critical debt: none. High debt blocks claims of a verified build but not preservation of
this bootstrap source. It must be addressed before the first Android implementation.
