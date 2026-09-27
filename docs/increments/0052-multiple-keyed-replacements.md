# Increment 52: Multiple keyed replacements

- Date: 2026-09-27
- Status: Validation pending

## Acceptance criteria

- Replace any number of incompatible keyed siblings while preserving every compatible sibling at
  the same position.
- Assign fresh runtime identities to every replacement subtree.
- Detach and delete each old subtree descendant-first before creating and attaching its replacement
  at the same index.
- Reject replacement mixed with keyed movement and reject an insufficient operation budget without
  publishing partial state.
- Measure 100 distributed replacements among 1,000 siblings in the release gate.

## Delivered

- Replaced the single-replacement detector with a linear pure-replacement planner.
- Added a previous-key index used only for direct lookup, preventing reorder from being mistaken for
  replacement without depending on hash iteration order.
- Reused typed child indices, descendant-first deletion, subtree creation and the unpublished commit
  builder.
- Added exact mutation, identity, mixed-movement rejection, atomic-budget and real headless-host
  contracts.
- Added a provisional 5 ms budget for 100 distributed replacements among 1,000 siblings.
- Added no dependency, unsafe block or caller-assigned runtime identity.

The planner builds one previous-key index, then walks both sibling slices once. Its expected time
complexity is `O(n + m)`, and all mutation order comes from slice order rather than hash iteration.

## Validation evidence

Pending pinned Rust 1.85 CI validation.

## Remaining limitations

- Replacement combined with movement, insertion or removal remains unsupported.
- Unkeyed structural replacement remains unsupported.

## References

- [Rust `HashMap::get`](https://doc.rust-lang.org/std/collections/struct.HashMap.html#method.get)

## Next increment

Define the first deterministic mixed keyed structural contract without weakening identity or atomic
commit guarantees.
