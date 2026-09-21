#!/usr/bin/env python3
"""Run deterministic generated surface lifecycle sequences."""

from __future__ import annotations

import hashlib
import json
from typing import Any

if __package__:
    from .check_surface_lifecycle_fixtures import transition, validate_state
    from .deterministic_random import StableRandom
    from .surface_lifecycle_invariants import LifecycleInvariantError, verify_transition
else:
    from check_surface_lifecycle_fixtures import transition, validate_state
    from deterministic_random import StableRandom
    from surface_lifecycle_invariants import LifecycleInvariantError, verify_transition

SEEDS = (13, 29, 53, 89, 137, 199, 277, 367)
STEPS_PER_SEED = 100
SURFACE_SLOTS = 8


def _pick(handles: list[dict[str, int]], rng: StableRandom) -> dict[str, int]:
    return dict(handles[rng.index(len(handles))])


def _create(rng: StableRandom) -> dict[str, int | str]:
    return {"op": "create", "surface_id": rng.index(SURFACE_SLOTS) + 1}


def _action(
    step: int,
    state: dict[str, Any],
    stale: list[dict[str, int]],
    rng: StableRandom,
) -> dict[str, Any]:
    active = state["active"]
    phase = step % 7
    if phase in {0, 6}:
        return _create(rng)
    if phase == 1:
        return {"op": "callback", "handle": _pick(active, rng)} if active else _create(rng)
    if phase == 2:
        if active:
            return {"op": "create", "surface_id": _pick(active, rng)["surface_id"]}
        return _create(rng)
    if phase == 3:
        return {"op": "dispose", "handle": _pick(active, rng)} if active else _create(rng)
    if phase == 4:
        handles = stale if stale else active
        return {"op": "callback", "handle": _pick(handles, rng)} if handles else _create(rng)
    handles = stale if stale else active
    return {"op": "dispose", "handle": _pick(handles, rng)} if handles else _create(rng)


def run_campaign(
    seeds: tuple[int, ...] = SEEDS, steps_per_seed: int = STEPS_PER_SEED
) -> dict[str, Any]:
    """Run fixed-seed lifecycle sequences and return reproducible metrics."""
    if steps_per_seed <= 0:
        raise ValueError("steps_per_seed must be positive")
    digest = hashlib.sha256()
    outcomes: dict[str, int] = {}
    rejection_codes: dict[str, int] = {}
    created_total = 0
    disposed_total = 0
    accepted_callbacks = 0
    active_peak = 0

    for seed in seeds:
        rng = StableRandom(seed)
        state: dict[str, Any] = {"allocator": {"status": "available", "next": 1}, "active": []}
        stale: list[dict[str, int]] = []
        ever_created: set[tuple[int, int]] = set()
        highest_generation = 0

        for step in range(steps_per_seed):
            action = _action(step, state, stale, rng)
            next_state, output = transition(state, action)
            validate_state(next_state)
            verify_transition(state, action, next_state, output)
            result = output["result"]
            outcomes[result] = outcomes.get(result, 0) + 1

            if result == "created":
                handle = output["handle"]
                identity = (handle["surface_id"], handle["generation"])
                if identity in ever_created or handle["generation"] <= highest_generation:
                    raise LifecycleInvariantError("generation was reused or did not advance")
                ever_created.add(identity)
                highest_generation = handle["generation"]
                created_total += 1
            elif result == "disposed":
                stale.append(dict(output["handle"]))
                disposed_total += 1
            elif result == "callback_accepted":
                accepted_callbacks += 1
            else:
                code = output["code"]
                rejection_codes[code] = rejection_codes.get(code, 0) + 1

            active_peak = max(active_peak, len(next_state["active"]))
            digest.update(
                json.dumps(
                    {"before": state, "action": action, "after": next_state, "output": output},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            state = next_state

    required_outcomes = {"created", "disposed", "callback_accepted", "rejected"}
    required_rejections = {"STALE_SURFACE_HANDLE", "SURFACE_ALREADY_ACTIVE"}
    if set(outcomes) != required_outcomes or set(rejection_codes) != required_rejections:
        raise LifecycleInvariantError("campaign did not cover every lifecycle outcome")
    return {
        "seeds": len(seeds),
        "steps_per_seed": steps_per_seed,
        "actions": len(seeds) * steps_per_seed,
        "outcomes": dict(sorted(outcomes.items())),
        "rejection_codes": dict(sorted(rejection_codes.items())),
        "created": created_total,
        "disposed": disposed_total,
        "accepted_callbacks": accepted_callbacks,
        "active_peak": active_peak,
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    """Execute the full deterministic lifecycle campaign."""
    print(json.dumps(run_campaign(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
