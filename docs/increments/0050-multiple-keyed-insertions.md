# Increment 50: Multiple keyed insertions

- Date: 2026-09-26
- Status: Pending repository CI

## Acceptance criteria

- Insert any number of new keyed siblings when every previous child remains a compatible,
  order-preserving subsequence of the candidate.
- Preserve every existing runtime identity and allocate new identities only for inserted subtrees.
- Emit deterministic `Create` then `InsertChild` groups in candidate order.
- Reject insertion mixed with reorder, removal or replacement and reject an insufficient operation
  budget without publishing partial state.
- Measure 100 distributed insertions into a final list of 1,000 siblings in the release gate.

## Delivered

- Replaced the single-insertion detector with a linear pure-insertion planner.
- Reused the existing subtree creation path, typed operation limit and unpublished commit builder.
- Added exact mutation, identity, ambiguity, atomic-budget and real headless-host contracts.
- Added a provisional 5 ms budget for 100 distributed insertions among 1,000 final siblings.
- Added no dependency, unsafe block or caller-assigned runtime identity.

The planner walks the previous and candidate slices once in their defined iteration order. Its time
complexity is `O(n + m)` and its result does not depend on hashing or unordered iteration.

## Validation evidence

Repository CI evidence will be recorded before this increment is merged.

## Remaining limitations

- Insertion combined with movement, removal or replacement remains unsupported.
- Multiple removals and replacements remain unsupported.
- Unkeyed structural insertion remains unsupported.

## References

- [Rust slice iteration](https://doc.rust-lang.org/std/primitive.slice.html#method.iter)

## Next increment

Define deterministic ordering and identity preservation for pure multiple keyed removals before
extending production reconciliation.
