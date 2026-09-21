#!/usr/bin/env python3
"""Run the reviewed Android container ownership scenarios."""

from __future__ import annotations

import copy
import json
from pathlib import Path

try:
    from scripts.android_container_model import (
        AndroidContainerViolation,
        ContainerRegistry,
        apply_action,
    )
    from scripts.android_container_invariants import validate_state, verify_transition
except ModuleNotFoundError:
    from android_container_model import (
        AndroidContainerViolation,
        ContainerRegistry,
        apply_action,
    )
    from android_container_invariants import validate_state, verify_transition


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "android-container" / "v1" / "contract.json"
SCENARIOS = ROOT / "contracts" / "android-container" / "v1" / "scenarios.json"
EXPECTED_CONTRACT = {
    "contract_version": 1,
    "threading": "main_only",
    "identity_range": "positive_kotlin_long",
    "states": ["RESERVED", "ATTACHED"],
    "actions": ["claim", "attach_succeeded", "attach_failed", "release"],
    "effects": [
        "ADD_ROOT",
        "REMOVE_ROOT",
        "REMOVE_STALE_ROOT",
        "CANCEL_ATTACH",
        "DROP_STALE_RESULT",
        "DROP_STALE_RELEASE",
        "NONE",
    ],
    "errors": [
        "WRONG_THREAD",
        "INVALID_ID",
        "CONTAINER_ALREADY_OWNED",
        "ROOT_NOT_DETACHED",
        "MOUNT_ID_EXHAUSTED",
    ],
    "invariants": [
        "one_current_host_per_container",
        "one_container_per_attached_root",
        "mount_ids_are_positive_monotonic_and_never_reused",
        "release_is_idempotent",
        "attached_root_is_removed_exactly_once",
        "stale_results_never_mutate_current_binding",
        "container_can_be_reclaimed_after_release",
        "all_view_hierarchy_effects_run_on_main",
    ],
}


def validate_contract(path: Path = CONTRACT) -> None:
    """Reject any unreviewed change to the closed ownership vocabulary."""
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract != EXPECTED_CONTRACT:
        raise ValueError("Android container contract drift")


def run_scenarios(path: Path = SCENARIOS) -> dict[str, int]:
    """Execute the closed scenario corpus and return stable metrics."""
    validate_contract()
    corpus = json.loads(path.read_text(encoding="utf-8"))
    if set(corpus) != {"contract_version", "scenarios"} or corpus["contract_version"] != 1:
        raise ValueError("invalid Android container scenario corpus")
    action_count = 0
    observed_effects: set[str] = set()
    observed_errors: set[str] = set()
    for scenario in corpus["scenarios"]:
        if set(scenario) != {"name", "actions", "effects", "errors"}:
            raise ValueError("Android container scenario fields are not closed")
        if not len(scenario["actions"]) == len(scenario["effects"]) == len(scenario["errors"]):
            raise ValueError(f"length mismatch: {scenario['name']}")
        model = ContainerRegistry()
        for action, expected_effect, expected_error in zip(
            scenario["actions"], scenario["effects"], scenario["errors"], strict=True
        ):
            previous = copy.deepcopy(model)
            before = previous.snapshot()
            effect = None
            error = None
            try:
                effect = apply_action(model, action)
            except AndroidContainerViolation as violation:
                error = violation.code
            validate_state(model)
            verify_transition(previous, action, model, effect, error)
            if error is not None and model.snapshot() != before:
                raise AssertionError(f"rejection mutated state: {scenario['name']}")
            effect_type = effect["type"] if effect is not None else None
            if effect_type != expected_effect or error != expected_error:
                raise AssertionError(
                    f"unexpected result in {scenario['name']}: "
                    f"effect={effect_type!r}, error={error!r}"
                )
            if effect_type is not None:
                observed_effects.add(effect_type)
            if error is not None:
                observed_errors.add(error)
            action_count += 1
    if observed_effects != set(EXPECTED_CONTRACT["effects"]):
        raise AssertionError("Android container effect coverage is incomplete")
    scenario_errors = set(EXPECTED_CONTRACT["errors"]) - {"MOUNT_ID_EXHAUSTED"}
    if observed_errors != scenario_errors:
        raise AssertionError("Android container error coverage is incomplete")
    return {"scenarios": len(corpus["scenarios"]), "actions": action_count}


def main() -> int:
    metrics = run_scenarios()
    print(
        "Android container fixtures passed: "
        f"{metrics['scenarios']} scenarios, {metrics['actions']} actions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
