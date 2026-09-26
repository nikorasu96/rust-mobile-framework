# Performance policy

Performance claims require measurements from a release build on identified hardware.
Debug-build numbers and unlabelled wall-clock results are not accepted as evidence.

## Foundation scenario

`rmf-bench` constructs a deterministic linear tree containing 1,000 nodes. It measures
100 iterations of complete structural validation and 100 mounts through the headless
renderer. The executable has no benchmarking or serialization dependency.

Run it with:

```bash
cargo run --release -p rmf-bench
```

## Provisional host budgets

| Metric | Initial gate | Scope |
| --- | ---: | --- |
| Validation average, 1,000 nodes | <= 1 ms | Host release build |
| Headless mount average, 1,000 nodes | <= 2 ms | Host release build |
| One keyed move, 1,000 siblings | <= 5 ms | Pure reconciliation, host release build |
| One keyed insertion, 1,000 final siblings | <= 5 ms | Pure reconciliation, host release build |
| One keyed removal, 1,000 initial siblings | <= 5 ms | Pure reconciliation, host release build |
| One keyed replacement, 1,000 siblings | <= 5 ms | Pure reconciliation, host release build |
| Serialized headless frame | <= 2 MiB | Functional allocation guard |

These are engineering guardrails, not Android product SLOs. Baseline hardware, warmup,
variance, percentiles, peak RSS, allocation counts, JNI latency, frame timing and binary
size gates must be established when the corresponding environment exists. Averages are
kept only for this dependency-free bootstrap and must not be presented as tail latency.

## Reconciliation specification

The language-independent oracle builds one key-to-index table per sibling list and uses
one expected constant-time lookup for each keyed candidate. A deterministic regression
reverses 2,048 keyed siblings and verifies that every existing identity is selected once.
Production Rust gates exercise one last-to-first keyed movement and one middle keyed insertion,
removal and replacement across 1,000 siblings for 100 preparations each. These averages guard
against accidental quadratic work; they are not tail-latency claims or general reorder evidence.

## Rules

1. Compare results only on named, equivalent hardware and toolchains.
2. Record compiler version, profile, target triple, CPU, OS and sample count.
3. Run warmup and percentile-capable benchmarks before optimizing runtime algorithms.
4. Treat a budget failure as evidence to investigate, not permission to raise the budget.
5. Preserve correctness tests alongside every optimization.
