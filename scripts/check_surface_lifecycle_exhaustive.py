#!/usr/bin/env python3
"""Exhaustively explore a bounded surface lifecycle domain."""

from __future__ import annotations

import hashlib
import json
from typing import Any

if __package__:
    from .check_surface_lifecycle_fixtures import transition, validate_state
    from .surface_lifecycle_invariants import verify_transition
else:
    from check_surface_lifecycle_fixtures import transition, validate_state
    from surface_lifecycle_invariants import verify_transition

MAX_DEPTH = 6
SURFACE_IDS = (1, 2)
HANDLE_GENERATIONS = (1, 2, 3, 4)


def _state_key(state: dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def _actions() -> tuple[dict[str, Any], ...]:
    actions: list[dict[str, Any]] = [
        {"op": "create", "surface_id": surface_id} for surface_id in SURFACE_IDS
    ]
    for operation in ("callback", "dispose"):
        for surface_id in SURFACE_IDS:
            for generation in HANDLE_GENERATIONS:
                actions.append(
                    {
                        "op": operation,
                        "handle": {"surface_id": surface_id, "generation": generation},
                    }
                )
    return tuple(actions)


def explore(max_depth: int = MAX_DEPTH) -> dict[str, Any]:
    """Check every state/action pair reachable within the bounded domain."""
    if max_depth <= 0:
        raise ValueError("max_depth must be positive")
    initial: dict[str, Any] = {"allocator": {"status": "available", "next": 1}, "active": []}
    frontier = {_state_key(initial): initial}
    all_states = dict(frontier)
    reachable_by_depth = [1]
    transitions_checked = 0
    outcomes: dict[str, int] = {}
    rejection_codes: dict[str, int] = {}
    active_peak = 0
    digest = hashlib.sha256()
    actions = _actions()

    for depth in range(max_depth):
        next_frontier: dict[str, dict[str, Any]] = {}
        for key in sorted(frontier):
            state = frontier[key]
            for action in actions:
                next_state, output = transition(state, action)
                validate_state(next_state)
                verify_transition(state, action, next_state, output)
                next_key = _state_key(next_state)
                next_frontier[next_key] = next_state
                all_states[next_key] = next_state
                result = output["result"]
                outcomes[result] = outcomes.get(result, 0) + 1
                if result == "rejected":
                    code = output["code"]
                    rejection_codes[code] = rejection_codes.get(code, 0) + 1
                active_peak = max(active_peak, len(next_state["active"]))
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

    required_outcomes = {"created", "disposed", "callback_accepted", "rejected"}
    required_rejections = {"STALE_SURFACE_HANDLE", "SURFACE_ALREADY_ACTIVE"}
    if set(outcomes) != required_outcomes or set(rejection_codes) != required_rejections:
        raise RuntimeError("bounded exploration did not cover every lifecycle outcome")
    return {
        "max_depth": max_depth,
        "surface_ids": len(SURFACE_IDS),
        "handle_generations": len(HANDLE_GENERATIONS),
        "actions_per_state": len(actions),
        "reachable_by_depth": reachable_by_depth,
        "unique_states": len(all_states),
        "transitions_checked": transitions_checked,
        "outcomes": dict(sorted(outcomes.items())),
        "rejection_codes": dict(sorted(rejection_codes.items())),
        "active_peak": active_peak,
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    """Run the bounded exhaustive lifecycle exploration."""
    print(json.dumps(explore(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
