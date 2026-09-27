# Increment 49: General keyed sibling reorder

- Date: 2026-09-26
- Status: Pending repository CI

## Acceptance criteria

- Reorder any permutation of fully keyed, type-compatible siblings without replacing identities.
- Emit a deterministic sequence of valid `MoveChild` operations consumable by the real host port.
- Avoid quadratic position maintenance and bound temporary memory.
- Reject an insufficient operation budget without publishing partial state.
- Measure a complete reversal of 1,000 siblings in the release gate.

## Delivered

- Added a per-sibling key-to-original-index table used only for lookup, never hash iteration.
- Added a Fenwick order-statistics index for live-position calculation.
- Preserved the existing single-move output and generalized wider permutations to `O(n log n)`
  planning time with `O(n)` temporary memory.
- Added exact two-move, reverse-order determinism, budget rejection and headless-host contracts.
- Added a provisional 10 ms budget for reversing 1,000 fully keyed siblings.
- Resolved TD-006 without adding dependencies or unsafe code.

The standard-library `HashMap` remains randomly seeded for HashDoS resistance. Deterministic
output is retained because reconciliation performs only direct key lookup and emits mutations in
candidate order; it never observes map iteration order.

## Validation evidence

Repository CI evidence will be recorded before this increment is merged.

## Remaining limitations

- Multiple insertions, removals or replacements in one sibling list remain unsupported.
- Reorder mixed with insertion/removal/replacement remains unsupported.
- Unkeyed structural reorder remains unsupported.

## References

- [Rust `HashMap`](https://doc.rust-lang.org/std/collections/struct.HashMap.html)
- [Rust collection performance](https://doc.rust-lang.org/std/collections/)

## Next increment

Select one mixed keyed structural case and define its ordering/identity contract before extending
production reconciliation.
