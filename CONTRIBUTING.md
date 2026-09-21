# Contributing

1. Start from an acceptance criterion and change one coherent vertical slice.
2. Preserve dependency direction in `docs/ARCHITECTURE.md`.
3. Add tests that observe behavior through public boundaries.
4. Run every command in the README before review.
5. Document material decisions as ADRs and user-visible changes in `CHANGELOG.md`.
6. Do not add unsafe code outside a dedicated FFI crate and approved ADR.
7. Do not merge placeholders, deceptive mocks, ignored failures, or critical debt.

Prefer small traits located with their consumer. Add abstractions only after a real
second implementation or a boundary that must be isolated.

