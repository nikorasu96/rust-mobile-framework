# Commit-application contract fixtures v1

These fixtures specify runtime promotion and recovery independently of a renderer or platform.
Each fixture starts from a surface state, executes ordered actions and compares every typed
outcome plus the final state.

Run them with:

```bash
python3 scripts/check_commit_state_fixtures.py
python3 scripts/check_commit_state_sequences.py
python3 scripts/check_commit_state_exhaustive.py
```

States and actions are closed objects. A successful host result promotes the target revision.
A safe rejection returns to the base revision. A possibly partial host failure blocks commits
until a full remount restores the last confirmed revision. The model contains no native mock;
it executes the state-transition contract defined by ADR-0004.

The eight reviewed fixtures provide readable examples. A complementary fixed-seed campaign
executes 800 generated actions across all seven action types and checks promotion, confirmed
revision and recovery invariants after every transition. Its digest makes the sequence exactly
replayable; it is deterministic property-style testing rather than coverage-guided fuzzing.

The bounded explorer complements sampling by applying nine semantic action variants to every
reachable state at each depth. Equivalent states at the same depth are merged because future
behavior depends only on the closed state value. This proves the transition-local invariants for
the explored bound; it is not an unbounded formal proof or a native adapter test.
