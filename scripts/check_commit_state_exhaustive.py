#!/usr/bin/env python3
"""Exhaustively explore bounded commit-state transitions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

if __package__:
    from .check_commit_state_fixtures import transition, validate_state
    from .commit_state_invariants import confirmed_revision, verify_transition
else:
    from check_commit_state_fixtures import transition, validate_state
    from commit_state_invariants import confirmed_revision, verify_transition

MAX_DEPTH = 8


def _state_key(state: dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def _actions(state: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    revision = confirmed_revision(state)
    stale = revision - 1 if revision > 0 else 1
    return (
        {"op": "begin_apply", "base_revision": revision, "target_revision": revision + 1},
        {"op": "begin_apply", "base_revision": stale, "target_revision": stale + 1},
        {"op": "begin_apply", "base_revision": revision, "target_revision": revision + 2},
        {"op": "host_applied"},
        {"op": "host_rejected", "code": "HOST_REJECTED"},
        {"op": "host_failed", "code": "HOST_FAILED"},
        {"op": "begin_remount"},
        {"op": "remount_succeeded"},
        {"op": "remount_failed", "code": "REMOUNT_FAILED"},
    )


def explore(max_depth: int = MAX_DEPTH) -> dict[str, Any]:
    """Explore every reachable state/action pair through ``max_depth`` steps."""
    if max_depth <= 0:
        raise ValueError("max_depth must be positive")
    initial: dict[str, Any] = {"state": "ready", "revision": 0}
    frontier = {_state_key(initial): initial}
    all_states = dict(frontier)
    reachable_by_depth = [len(frontier)]
    state_types = {"ready": 1}
    action_types: dict[str, int] = {}
    outcome_types: dict[str, int] = {}
    transitions_checked = 0
    digest = hashlib.sha256()

    for depth in range(max_depth):
        next_frontier: dict[str, dict[str, Any]] = {}
        for key in sorted(frontier):
            state = frontier[key]
            for action in _actions(state):
                next_state, output = transition(state, action)
                validate_state(next_state)
                verify_transition(state, action, next_state, output)
                next_key = _state_key(next_state)
                next_frontier[next_key] = next_state
                if next_key not in all_states:
                    all_states[next_key] = next_state
                    name = next_state["state"]
                    state_types[name] = state_types.get(name, 0) + 1
                action_name = action["op"]
                outcome_name = output["result"]
                action_types[action_name] = action_types.get(action_name, 0) + 1
                outcome_types[outcome_name] = outcome_types.get(outcome_name, 0) + 1
                transitions_checked += 1
                digest.update(
                    json.dumps(
                        {
                            "depth": depth,
                            "before": state,
                            "action": action,
                            "after": next_state,
                            "output": output,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                )
        frontier = next_frontier
        reachable_by_depth.append(len(frontier))

    required_states = {"ready", "applying", "failed", "remounting"}
    if set(state_types) != required_states:
        missing = sorted(required_states.difference(state_types))
        raise RuntimeError(f"exploration did not reach state types: {missing}")
    required_actions = {
        "begin_apply",
        "host_applied",
        "host_rejected",
        "host_failed",
        "begin_remount",
        "remount_succeeded",
        "remount_failed",
    }
    if set(action_types) != required_actions:
        missing = sorted(required_actions.difference(action_types))
        raise RuntimeError(f"exploration did not cover actions: {missing}")

    return {
        "max_depth": max_depth,
        "reachable_by_depth": reachable_by_depth,
        "unique_states": len(all_states),
        "state_types": dict(sorted(state_types.items())),
        "transitions_checked": transitions_checked,
        "action_types": dict(sorted(action_types.items())),
        "outcome_types": dict(sorted(outcome_types.items())),
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    """Run the bounded exhaustive exploration and print measured evidence."""
    print(json.dumps(explore(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
