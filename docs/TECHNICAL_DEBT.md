# Technical debt register

| ID | Priority | Item | Exit criterion |
| --- | --- | --- | --- |
| TD-001 | Medium | Rust toolchain unavailable locally; compilation depends on repository CI | Provide a pinned local toolchain or keep every Rust increment gated by successful CI |
| TD-003 | Medium | Legacy full-tree rendering allocates a diagnostic string recursively | Remove it with the remaining bootstrap renderer contract after committed-path equivalence is verified |
| TD-004 | Medium | Committed-path benchmark reports averages only and has no hardware baseline | Add warmup, percentiles and recorded release baseline when Rust execution is available |
| TD-005 | High | Example and benchmark use committed identities, but legacy renderer tests and `Runtime::mount` still accept caller-assigned IDs | Replace the remaining renderer/runtime contracts, then remove the bootstrap tree, renderer port and mount use case before Android work |
| TD-006 | Medium | Production handles one keyed move, insertion, removal or replacement linearly; general wide reorders still need order maintenance | Select and benchmark a non-quadratic multi-move strategy before general reorder support |

Critical debt: none. High debt blocks the Android implementation until the
declarative/committed split is complete. Rust build claims require successful repository CI
while the local toolchain remains absent.
