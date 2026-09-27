# Increment 51: Multiple keyed removals

- Date: 2026-09-26
- Status: Complete

## Acceptance criteria

- Remove any number of keyed siblings when the candidate is a compatible, order-preserving
  subsequence of the previous children.
- Preserve every surviving runtime identity.
- Emit each `RemoveChild` with the live index after earlier removals, then delete that detached
  subtree descendant-first.
- Reject removal mixed with insertion, movement or replacement and reject an insufficient operation
  budget without publishing partial state.
- Measure 100 distributed removals from 1,000 siblings in the release gate.

## Delivered

- Replaced the single-removal detector with a linear pure-removal planner.
- Reused typed child indices, descendant-first subtree deletion and the unpublished commit builder.
- Added exact mutation, identity, mixed-change rejection, atomic-budget and real headless-host
  contracts.
- Added a provisional 5 ms budget for 100 distributed removals from 1,000 initial siblings.
- Added no dependency, unsafe block or caller-assigned runtime identity.

The planner walks the previous and candidate slices once in their defined iteration order. The
number of surviving children already emitted is the current live removal index. Its time complexity
is `O(n + m)` and its result does not depend on hashing or unordered iteration.

## Validation evidence

GitHub Actions run
[`36296153729`](https://github.com/nikorasu96/rust-mobile-framework/actions/runs/36296153729)
passed with the pinned Rust 1.85 toolchain:

- `cargo fmt --all --check`
- workspace Clippy with warnings denied
- 62 Rust tests
- workspace rustdoc with warnings denied
- architecture policy and 85 independent contract regressions
- release performance gate: 101,600 ns average for 100 distributed removals from 1,000 initial
  siblings (5,000,000 ns budget)

## Remaining limitations

- Removal combined with movement, insertion or replacement remains unsupported.
- Multiple replacements remain unsupported.
- Unkeyed structural removal remains unsupported.

## References

- [Rust `Iterator::enumerate`](https://doc.rust-lang.org/std/iter/trait.Iterator.html#method.enumerate)

## Next increment

Define and implement deterministic multiple keyed replacement while keeping mixed structural
changes explicitly unsupported.
