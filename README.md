# Rust Mobile Framework (working title)

An experimental mobile UI framework with a safe Rust core, thin native platform
adapters, and a future declarative TypeScript API. Android is the first target.

This repository is **not React Native compatible yet**. Compatibility is tracked by
observable capability in [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).

## Current verified slice

The first slice models a declarative UI tree, validates structural invariants, mounts
it through a renderer port, and provides a deterministic headless adapter. The slice
contains no native or third-party dependency, keeping architectural validation cheap.

```text
declarative tree -> validation -> runtime port -> headless renderer
```

## Repository map

- `crates/rmf-core`: platform-independent UI model and invariants.
- `crates/rmf-reconciliation`: compiled pure commit service for runtime-owned identities,
  immutable snapshots and deterministic mutation batches.
- `crates/rmf-runtime`: use-case orchestration and renderer ports.
- `adapters/rmf-renderer-headless`: deterministic outbound adapter for tests/tools.
- `examples/hello-headless`: executable composition root.
- `platforms/android`: compile-gated Android module, ABI and artifact topology from ADR-0007.
- `platforms`: later platform adapters; iOS begins only after Android gates.
- `packages`: reserved for public TypeScript packages.
- `docs`: architecture, decisions, roadmap, compatibility and debt.
- `contracts`: executable, language-independent reconciliation, lifecycle and Android FFI
  specifications.

## Quality commands

Requires Rust 1.85.0, pinned by `rust-toolchain.toml`.

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-targets --all-features
cargo doc --workspace --no-deps
cargo deny check
python3 scripts/check_architecture.py
python3 scripts/check_android_topology.py
python3 scripts/check_android_public_api.py
python3 scripts/check_android_container_fixtures.py
python3 scripts/check_android_container_exhaustive.py
python3 scripts/check_android_host_composition.py
python3 scripts/check_android_facade_fixtures.py
python3 scripts/check_android_facade_exhaustive.py
python3 -m unittest discover -s scripts/tests
python3 scripts/check_reconciliation_fixtures.py
python3 scripts/check_reconciliation_sequences.py
python3 scripts/check_commit_state_fixtures.py
python3 scripts/check_commit_state_sequences.py
python3 scripts/check_commit_state_exhaustive.py
python3 scripts/check_surface_lifecycle_fixtures.py
python3 scripts/check_surface_lifecycle_sequences.py
python3 scripts/check_surface_lifecycle_exhaustive.py
python3 scripts/check_android_ffi_fixtures.py
python3 scripts/check_android_ffi_frame_corpus.py
python3 scripts/check_android_ffi_body_corpus.py
python3 scripts/check_android_ffi_mutations.py
cargo run --release -p rmf-bench
```

The same Rust gates run on every pull request before an increment can reach `main`.

Run the first vertical slice:

```bash
cargo run -p hello-headless
```

The example validates a caller-declared tree without runtime IDs, reconciles it into an immutable
snapshot, applies the resulting mutation batch atomically, and prints the confirmed host summary.

## Status

Pre-alpha architecture validation. Do not use in production.

Python 3.11+ runs dependency, golden-contract and generated-invariant checks without
third-party Python packages.

Performance methodology and provisional gates are documented in
[`docs/PERFORMANCE.md`](docs/PERFORMANCE.md).
