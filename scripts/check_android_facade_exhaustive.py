#!/usr/bin/env python3
"""Exhaustively explore a bounded Android facade action domain."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

try:
    from scripts.android_facade_invariants import validate_state, verify_transition
    from scripts.android_facade_model import AndroidFacadeViolation, FacadeState, apply_action
    from scripts.check_android_facade_fixtures import load_contract
except ModuleNotFoundError:
    from android_facade_invariants import validate_state, verify_transition
    from android_facade_model import AndroidFacadeViolation, FacadeState, apply_action
    from check_android_facade_fixtures import load_contract


MAX_DEPTH = 7
HANDLES = ((1, 1), (1, 2))
SEQUENCES = (1, 2)


@dataclass
class ExplorationNode:
    """Facade state plus path facts needed for temporal invariants."""

    model: FacadeState
    create_calls: int = 0
    dispose_calls: int = 0
    close_requested: bool = False

    def key(self) -> str:
        value = {
            "model": self.model.snapshot(),
            "create_calls": self.create_calls,
            "dispose_calls": self.dispose_calls,
            "close_requested": self.close_requested,
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":"))


def actions() -> tuple[dict[str, Any], ...]:
    """Return the closed, bounded action alphabet in canonical order."""
    result: list[dict[str, Any]] = [
        {"type": "request_create", "caller_thread": thread}
        for thread in ("main", "worker")
    ]
    result.extend(
        {"type": "main_drain_create", "caller_thread": thread}
        for thread in ("main", "worker")
    )
    for thread in ("main", "worker"):
        for surface_id, generation in HANDLES:
            result.append(
                {
                    "type": "native_create_succeeded",
                    "caller_thread": thread,
                    "surface_id": surface_id,
                    "generation": generation,
                }
            )
    result.append(
        {
            "type": "native_create_succeeded",
            "caller_thread": "main",
            "surface_id": 0,
            "generation": 1,
        }
    )
    for thread in ("main", "worker"):
        for reason in ("HOST_UNAVAILABLE", "HOST_INTERNAL"):
            result.append(
                {
                    "type": "native_create_failed",
                    "caller_thread": thread,
                    "reason": reason,
                }
            )
    result.extend(
        {"type": "request_close", "caller_thread": thread}
        for thread in ("main", "worker")
    )
    result.extend(
        {"type": "main_drain_close", "caller_thread": thread}
        for thread in ("main", "worker")
    )
    result.extend(
        {"type": "native_dispose_succeeded", "caller_thread": thread}
        for thread in ("main", "worker")
    )
    for thread in ("main", "worker"):
        for reason in ("HOST_UNAVAILABLE", "HOST_INTERNAL"):
            result.append(
                {
                    "type": "native_dispose_failed",
                    "caller_thread": thread,
                    "reason": reason,
                }
            )
    for thread in ("main", "worker"):
        for surface_id, generation in HANDLES:
            for sequence in SEQUENCES:
                result.append(
                    {
                        "type": "native_callback",
                        "caller_thread": thread,
                        "surface_id": surface_id,
                        "generation": generation,
                        "sequence": sequence,
                    }
                )
    result.append(
        {
            "type": "native_callback",
            "caller_thread": "main",
            "surface_id": 1,
            "generation": 1,
            "sequence": 0,
        }
    )
    return tuple(result)


def transition(
    node: ExplorationNode, action: dict[str, Any]
) -> tuple[ExplorationNode, dict[str, Any] | None, str | None]:
    """Apply one action to an isolated node and retain temporal counters."""
    current = copy.deepcopy(node)
    effect = None
    error = None
    try:
        effect = apply_action(current.model, action)
    except AndroidFacadeViolation as violation:
        error = violation.code
    if effect is not None:
        if effect["type"] == "CALL_NATIVE_CREATE":
            current.create_calls += 1
        elif effect["type"] == "CALL_NATIVE_DISPOSE":
            current.dispose_calls += 1
        if action["type"] == "request_close":
            current.close_requested = True
    return current, effect, error


def explore(max_depth: int = MAX_DEPTH) -> dict[str, Any]:
    """Verify every reachable node/action pair inside the bounded domain."""
    if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth <= 0:
        raise ValueError("max_depth must be a positive integer")
    contract = load_contract()
    registered_states = set(contract["states"])
    registered_errors = set(contract["errors"])
    registered_effects = set(contract["effects"])
    action_alphabet = actions()
    initial = ExplorationNode(FacadeState())
    frontier = {initial.key(): initial}
    all_nodes = dict(frontier)
    reachable_by_depth = [1]
    state_types = {initial.model.state}
    effects: dict[str, int] = {}
    errors: dict[str, int] = {}
    transitions_checked = 0
    digest = hashlib.sha256()

    for depth in range(max_depth):
        next_frontier: dict[str, ExplorationNode] = {}
        for key in sorted(frontier):
            node = frontier[key]
            for action in action_alphabet:
                current, effect, error = transition(node, action)
                validate_state(current.model, registered_states)
                verify_transition(
                    node.model,
                    action,
                    current.model,
                    effect,
                    error,
                    close_was_requested=node.close_requested,
                    create_calls=current.create_calls,
                    dispose_calls=current.dispose_calls,
                )
                if error is not None:
                    if error not in registered_errors:
                        raise RuntimeError("exploration produced an unregistered error")
                    errors[error] = errors.get(error, 0) + 1
                else:
                    effect_type = effect["type"]
                    if effect_type not in registered_effects:
                        raise RuntimeError("exploration produced an unregistered effect")
                    effects[effect_type] = effects.get(effect_type, 0) + 1
                current_key = current.key()
                next_frontier[current_key] = current
                all_nodes[current_key] = current
                state_types.add(current.model.state)
                transitions_checked += 1
                digest.update(
                    json.dumps(
                        {
                            "depth": depth,
                            "before": json.loads(node.key()),
                            "action": action,
                            "after": json.loads(current.key()),
                            "effect": effect,
                            "error": error,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                )
        frontier = next_frontier
        reachable_by_depth.append(len(frontier))

    if state_types != registered_states:
        raise RuntimeError("bounded exploration did not reach every facade state")
    if set(effects) != registered_effects:
        raise RuntimeError("bounded exploration did not cover every facade effect")
    if set(errors) != registered_errors:
        raise RuntimeError("bounded exploration did not cover every facade error")
    return {
        "max_depth": max_depth,
        "actions_per_node": len(action_alphabet),
        "reachable_by_depth": reachable_by_depth,
        "unique_nodes": len(all_nodes),
        "state_types": sorted(state_types),
        "transitions_checked": transitions_checked,
        "effects": dict(sorted(effects.items())),
        "errors": dict(sorted(errors.items())),
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    """Run the bounded exhaustive facade exploration."""
    print(json.dumps(explore(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
