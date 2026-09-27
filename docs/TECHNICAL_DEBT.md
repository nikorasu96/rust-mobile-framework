# Technical debt register

| ID | Priority | Item | Exit criterion |
| --- | --- | --- | --- |
| TD-001 | Medium | Rust toolchain unavailable locally; compilation depends on repository CI | Provide a pinned local toolchain or keep every Rust increment gated by successful CI |
| TD-004 | Medium | Committed-path benchmark reports averages only and has no hardware baseline | Add warmup, percentiles and recorded release baseline when Rust execution is available |

Critical and high debt: none. Rust build claims require successful repository CI while the local
toolchain remains absent.

## Resolved

| ID | Date | Resolution |
| --- | --- | --- |
| TD-003 | 2026-09-26 | Removed the recursive full-tree diagnostic renderer in `0.2.0-alpha.1` after the headless mutation adapter and committed-path benchmark replaced its evidence |
| TD-005 | 2026-09-26 | Removed caller-assigned runtime identities, `Runtime::mount` and the bootstrap renderer after migrating example, benchmark and contracts |
| TD-006 | 2026-09-26 | Implemented deterministic general keyed reorder planning with hash lookup plus a Fenwick order-statistics index and a 1,000-sibling reverse-order benchmark |
