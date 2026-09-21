#!/usr/bin/env python3
"""Exhaustively explore a bounded Android container action domain."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

try:
    from scripts.android_container_invariants import validate_state, verify_transition
    from scripts.android_container_model import (
        MAX_KOTLIN_LONG,
        AndroidContainerViolation,
        ContainerRegistry,
        apply_action,
    )
    from scripts.check_android_container_fixtures import EXPECTED_CONTRACT, validate_contract
except ModuleNotFoundError:
    from android_container_invariants import validate_state, verify_transition
    from android_container_model import (
        MAX_KOTLIN_LONG,
        AndroidContainerViolation,
        ContainerRegistry,
        apply_action,
    )
    from check_android_container_fixtures import EXPECTED_CONTRACT, validate_contract


MAX_DEPTH = 5
CONTAINERS = (1, 2)
HOSTS = (10, 11)
MOUNTS = (1, 2, 3)
ROOTS = (100, 101)


def _key(model: ContainerRegistry) -> str:
    return json.dumps(model.snapshot(), sort_keys=True, separators=(",", ":"))


def actions() -> tuple[dict[str, Any], ...]:
    """Return the closed finite action alphabet in canonical order."""
    result: list[dict[str, Any]] = [
        {
            "type": "claim",
            "caller_thread": "main",
            "container_id": container_id,
            "host_id": host_id,
        }
        for container_id in CONTAINERS
        for host_id in HOSTS
    ]
    for container_id in CONTAINERS:
        for host_id in HOSTS:
            for mount_id in MOUNTS:
                for root_id in ROOTS:
                    result.append(
                        {
                            "type": "attach_succeeded",
                            "caller_thread": "main",
                            "container_id": container_id,
                            "host_id": host_id,
                            "mount_id": mount_id,
                            "root_id": root_id,
                        }
                    )
                for action_type in ("attach_failed", "release"):
                    result.append(
                        {
                            "type": action_type,
                            "caller_thread": "main",
                            "container_id": container_id,
                            "host_id": host_id,
                            "mount_id": mount_id,
                        }
                    )
    result.extend(
        [
            {"type": "claim", "caller_thread": "worker", "container_id": 1, "host_id": 10},
            {"type": "claim", "caller_thread": "main", "container_id": 0, "host_id": 10},
        ]
    )
    return tuple(result)


def transition(
    model: ContainerRegistry, action: dict[str, Any]
) -> tuple[ContainerRegistry, dict[str, Any] | None, str | None]:
    """Apply an action to an isolated state and retain rejection details."""
    current = copy.deepcopy(model)
    effect = None
    error = None
    try:
        effect = apply_action(current, action)
    except AndroidContainerViolation as violation:
        error = violation.code
    return current, effect, error


def explore(max_depth: int = MAX_DEPTH) -> dict[str, Any]:
    """Verify every reachable state/action pair in the bounded domain."""
    if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth <= 0:
        raise ValueError("max_depth must be a positive integer")
    validate_contract()
    alphabet = actions()
    normal = ContainerRegistry()
    exhausted = ContainerRegistry(next_mount_id=MAX_KOTLIN_LONG + 1)
    frontier = {_key(normal): normal, _key(exhausted): exhausted}
    all_states = dict(frontier)
    reachable_by_depth = [len(frontier)]
    state_types: set[str] = set()
    effects: dict[str, int] = {}
    errors: dict[str, int] = {}
    transitions_checked = 0
    digest = hashlib.sha256()

    for depth in range(max_depth):
        next_frontier: dict[str, ContainerRegistry] = {}
        for key in sorted(frontier):
            previous = frontier[key]
            for action in alphabet:
                current, effect, error = transition(previous, action)
                validate_state(current)
                verify_transition(previous, action, current, effect, error)
                if error is not None:
                    errors[error] = errors.get(error, 0) + 1
                else:
                    effect_type = effect["type"]
                    effects[effect_type] = effects.get(effect_type, 0) + 1
                state_types.update(
                    binding["state"] for binding in current.snapshot()["bindings"].values()
                )
                current_key = _key(current)
                next_frontier[current_key] = current
                all_states[current_key] = current
                transitions_checked += 1
                digest.update(
                    json.dumps(
                        {
                            "depth": depth,
                            "before": previous.snapshot(),
                            "action": action,
                            "after": current.snapshot(),
                            "effect": effect,
                            "error": error,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                )
        frontier = next_frontier
        reachable_by_depth.append(len(frontier))

    if state_types != set(EXPECTED_CONTRACT["states"]):
        raise RuntimeError("bounded exploration missed a binding state")
    if set(effects) != set(EXPECTED_CONTRACT["effects"]):
        raise RuntimeError("bounded exploration missed a container effect")
    if set(errors) != set(EXPECTED_CONTRACT["errors"]):
        raise RuntimeError("bounded exploration missed a container error")
    return {
        "max_depth": max_depth,
        "actions_per_state": len(alphabet),
        "reachable_by_depth": reachable_by_depth,
        "unique_states": len(all_states),
        "binding_states": sorted(state_types),
        "transitions_checked": transitions_checked,
        "effects": dict(sorted(effects.items())),
        "errors": dict(sorted(errors.items())),
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    """Run the bounded exhaustive container exploration."""
    print(json.dumps(explore(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
