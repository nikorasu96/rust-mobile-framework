#!/usr/bin/env python3
"""Generate deterministic commit-state transitions and verify safety invariants."""

from __future__ import annotations

import hashlib
import json
from typing import Any

if __package__:
    from .check_commit_state_fixtures import transition, validate_state
    from .commit_state_invariants import confirmed_revision, verify_transition
    from .deterministic_random import StableRandom
else:
    from check_commit_state_fixtures import transition, validate_state
    from commit_state_invariants import confirmed_revision, verify_transition
    from deterministic_random import StableRandom

SEEDS = (11, 23, 47, 83, 131, 197, 269, 359)
STEPS_PER_SEED = 100


def _begin_apply(state: dict[str, Any], variant: int) -> dict[str, Any]:
    revision = confirmed_revision(state)
    if variant == 0:
        return {"op": "begin_apply", "base_revision": revision, "target_revision": revision + 1}
    if variant == 1:
        stale = revision - 1 if revision > 0 else 1
        return {"op": "begin_apply", "base_revision": stale, "target_revision": stale + 1}
    return {"op": "begin_apply", "base_revision": revision, "target_revision": revision + 2}


def _action(state: dict[str, Any], rng: StableRandom) -> dict[str, Any]:
    name = state["state"]
    if name == "ready":
        return _begin_apply(state, rng.index(4) if rng.chance(0.35) else 0)
    if name == "applying":
        options = (
            {"op": "host_applied"},
            {"op": "host_rejected", "code": "HOST_REJECTED"},
            {"op": "host_failed", "code": "HOST_FAILED"},
            _begin_apply(state, 0),
        )
        return options[rng.index(len(options))]
    if name == "failed":
        return {"op": "begin_remount"} if rng.chance(0.65) else _begin_apply(state, 0)
    options = (
        {"op": "remount_succeeded"},
        {"op": "remount_failed", "code": "REMOUNT_FAILED"},
        _begin_apply(state, 0),
    )
    return options[rng.index(len(options))]


def run_campaign(
    seeds: tuple[int, ...] = SEEDS, steps_per_seed: int = STEPS_PER_SEED
) -> dict[str, Any]:
    """Run fixed-seed state-machine actions and return reproducible metrics."""
    if steps_per_seed <= 0:
        raise ValueError("steps_per_seed must be positive")
    digest = hashlib.sha256()
    action_types: dict[str, int] = {}
    outcome_types: dict[str, int] = {}
    promotions = 0
    recoveries = 0
    partial_failures = 0

    for seed in seeds:
        rng = StableRandom(seed)
        state: dict[str, Any] = {"state": "ready", "revision": 0}
        for _ in range(steps_per_seed):
            action = _action(state, rng)
            next_state, output = transition(state, action)
            validate_state(next_state)
            verify_transition(state, action, next_state, output)

            action_name = action["op"]
            outcome_name = output["result"]
            action_types[action_name] = action_types.get(action_name, 0) + 1
            outcome_types[outcome_name] = outcome_types.get(outcome_name, 0) + 1
            promotions += int(outcome_name == "commit_promoted")
            recoveries += int(outcome_name == "surface_restored")
            partial_failures += int(action_name == "host_failed")
            digest.update(
                json.dumps(
                    {"before": state, "action": action, "after": next_state, "output": output},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            state = next_state

    return {
        "seeds": len(seeds),
        "steps_per_seed": steps_per_seed,
        "actions": len(seeds) * steps_per_seed,
        "action_types": dict(sorted(action_types.items())),
        "outcome_types": dict(sorted(outcome_types.items())),
        "promotions": promotions,
        "partial_failures": partial_failures,
        "recoveries": recoveries,
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    """Execute the full deterministic campaign and print its measured summary."""
    print(json.dumps(run_campaign(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
