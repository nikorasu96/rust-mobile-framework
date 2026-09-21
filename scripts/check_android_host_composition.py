#!/usr/bin/env python3
"""Execute reviewed Android host composition scenarios."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

try:
    from scripts.android_host_composition_model import (
        ACTION_FIELDS,
        AndroidHostCompositionViolation,
        AndroidHostState,
        apply_action,
    )
except ModuleNotFoundError:
    from android_host_composition_model import (
        ACTION_FIELDS,
        AndroidHostCompositionViolation,
        AndroidHostState,
        apply_action,
    )


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "android-host" / "v1" / "contract.json"
SCENARIOS = ROOT / "contracts" / "android-host" / "v1" / "scenarios.json"
EXPECTED_OUTCOMES = [
    "CREATE_REQUESTED",
    "SURFACE_ACTIVE",
    "START_FAILED",
    "CLOSE_WAITING_NATIVE",
    "LATE_SURFACE_DISPOSED",
    "CLOSED",
    "CALLBACK_DELIVERED",
    "CALLBACK_DROPPED",
    "NONE",
]
EXPECTED_ERRORS = [
    "INVALID_ACTION",
    "WRONG_THREAD",
    "INVALID_TRANSITION",
    "INVALID_ID",
    "INTERNAL_INVARIANT",
]


def validate_invariants(model: AndroidHostState) -> None:
    """Reject any state that violates cross-contract ownership and lifetime rules."""
    snapshot = model.snapshot()
    bindings = cast(dict[str, dict[str, Any]], snapshot["containers"]["bindings"])
    active = cast(list[dict[str, int]], snapshot["surfaces"]["active"])
    facade = snapshot["facade"]
    if model.mount_id is not None:
        binding = bindings.get(str(model.container_id))
        if binding is None or binding != {
            "host_id": model.host_id,
            "mount_id": model.mount_id,
            "state": "ATTACHED",
            "root_id": model.root_id,
        }:
            raise AssertionError("owned mount is not the exact attached root")
    if facade["state"] in {"CREATING", "ACTIVE"} and model.mount_id is None:
        raise AssertionError("creating or active facade has no attached root")
    if facade["state"] == "ACTIVE":
        if facade["handle"] not in active:
            raise AssertionError("active facade has no exact live surface")
    if facade["state"] in {"CLOSED", "FAILED"} and model.mount_id is not None:
        raise AssertionError("terminal facade still owns a container")
    if facade["handle"] is not None and facade["state"] != "ACTIVE":
        raise AssertionError("non-active observable state retained a handle")


def _summary(model: AndroidHostState) -> dict[str, Any]:
    snapshot = model.snapshot()
    return {
        "facade": snapshot["facade"]["state"],
        "bindings": len(snapshot["containers"]["bindings"]),
        "active_surfaces": len(snapshot["surfaces"]["active"]),
        "mount_owned": model.mount_id is not None,
    }


def run_scenarios(path: Path = SCENARIOS) -> dict[str, Any]:
    """Run the closed scenario corpus and return stable coverage metrics."""
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    corpus = json.loads(path.read_text(encoding="utf-8"))
    if contract != {
        "contract_version": 1,
        "threading": "main_only",
        "actions": list(ACTION_FIELDS),
        "outcomes": EXPECTED_OUTCOMES,
        "errors": EXPECTED_ERRORS,
        "ordering": [
            "claim_container_before_attach_root",
            "attach_root_before_native_surface_create",
            "validate_surface_handle_before_facade_callback",
            "dispose_exact_surface_before_terminal_close",
        ],
        "invariants": [
            "active_facade_has_exact_attached_root_and_live_surface",
            "close_releases_only_the_owned_root",
            "late_create_after_close_is_immediately_disposed",
            "failed_start_leaves_no_owned_container_or_surface",
            "stale_callbacks_never_reach_the_facade",
            "foreign_container_and_surface_ownership_is_preserved",
            "all_composition_actions_run_on_main",
        ],
    }:
        raise ValueError("Android host contract drift")
    if corpus.get("contract_version") != 1:
        raise ValueError("unsupported Android host contract version")
    observed_outcomes: set[str] = set()
    observed_errors: set[str] = set()
    action_count = 0
    for scenario in corpus["scenarios"]:
        if set(scenario) != {"name", "actions", "outcomes", "errors", "final"}:
            raise ValueError("Android host scenario fields are not closed")
        if not len(scenario["actions"]) == len(scenario["outcomes"]) == len(scenario["errors"]):
            raise ValueError(f"scenario length mismatch: {scenario['name']}")
        model = AndroidHostState()
        for action, expected_outcome, expected_error in zip(
            scenario["actions"], scenario["outcomes"], scenario["errors"], strict=True
        ):
            before = copy.deepcopy(model.snapshot())
            outcome = None
            error = None
            try:
                outcome = apply_action(model, action)
            except AndroidHostCompositionViolation as violation:
                error = violation.code
            validate_invariants(model)
            if error is not None and model.snapshot() != before:
                raise AssertionError(f"rejection mutated state: {scenario['name']}")
            outcome_type = outcome["type"] if outcome is not None else None
            if outcome_type != expected_outcome or error != expected_error:
                raise AssertionError(
                    f"unexpected result in {scenario['name']}: "
                    f"outcome={outcome_type!r}, error={error!r}"
                )
            if outcome_type is not None:
                observed_outcomes.add(outcome_type)
            if error is not None:
                observed_errors.add(error)
            action_count += 1
        if _summary(model) != scenario["final"]:
            raise AssertionError(f"unexpected final state: {scenario['name']}")
    if observed_outcomes != set(EXPECTED_OUTCOMES):
        raise AssertionError("Android host outcome coverage is incomplete")
    return {
        "scenarios": len(corpus["scenarios"]),
        "actions": action_count,
        "outcomes": sorted(observed_outcomes),
        "errors": sorted(observed_errors),
    }


def main() -> int:
    """Run the reviewed Android host composition corpus."""
    metrics = run_scenarios()
    print(
        "Android host composition passed: "
        f"{metrics['scenarios']} scenarios, {metrics['actions']} actions, "
        f"{len(metrics['outcomes'])} outcomes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
