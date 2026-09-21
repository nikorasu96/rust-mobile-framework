#!/usr/bin/env python3
"""Run reviewed Android Kotlin facade lifecycle scenarios."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.android_facade_model import AndroidFacadeViolation, FacadeState, apply_action
except ModuleNotFoundError:
    from android_facade_model import AndroidFacadeViolation, FacadeState, apply_action


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIRECTORY = ROOT / "contracts" / "android-facade" / "v1"
CONTRACT_FIELDS = {
    "contract_version",
    "initial_state",
    "states",
    "actions",
    "effects",
    "errors",
    "threading",
    "invariants",
}
FIXTURE_FIELDS = {"contract_version", "name", "actions", "expected"}
EXPECTED_FIELDS = {"final_state", "effects", "error"}
EXPECTED_REGISTRIES = {
    "states": [
        "NEW", "CREATE_QUEUED", "CREATING", "ACTIVE", "CLOSE_QUEUED",
        "CLOSE_PENDING_CREATE", "CLOSING", "CLOSED", "FAILED",
    ],
    "actions": [
        "request_create", "main_drain_create", "native_create_succeeded",
        "native_create_failed", "request_close", "main_drain_close",
        "native_dispose_succeeded", "native_dispose_failed", "native_callback",
    ],
    "effects": [
        "CALL_NATIVE_CREATE", "POST_CREATE_TO_MAIN", "CANCEL_QUEUED_CREATE",
        "CALL_NATIVE_DISPOSE", "POST_CLOSE_TO_MAIN", "DELIVER_CALLBACK",
        "DROP_CALLBACK", "IGNORE_CANCELLED_TASK", "NONE",
    ],
    "errors": [
        "INVALID_TRANSITION", "INVALID_HANDLE", "INVALID_SEQUENCE", "WRONG_THREAD",
    ],
}


class AndroidFacadeContractViolation(Exception):
    """Raised when facade contract metadata is open or inconsistent."""


def load_contract(path: Path = CONTRACT_DIRECTORY / "contract.json") -> dict[str, Any]:
    """Load the closed facade registry."""
    contract = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict) or set(contract) != CONTRACT_FIELDS:
        raise AndroidFacadeContractViolation("invalid contract fields")
    if contract["contract_version"] != 1 or contract["initial_state"] != "NEW":
        raise AndroidFacadeContractViolation("unsupported contract")
    for registry in ("states", "actions", "effects", "errors", "invariants"):
        values = contract[registry]
        if not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values):
            raise AndroidFacadeContractViolation(f"invalid {registry}")
        if len(values) != len(set(values)):
            raise AndroidFacadeContractViolation(f"duplicate {registry}")
    for registry, expected in EXPECTED_REGISTRIES.items():
        if contract[registry] != expected:
            raise AndroidFacadeContractViolation(f"unexpected {registry}")
    expected_threading = {
        "public_requests": "marshal_to_main",
        "native_results": "main_only",
        "native_callbacks": "main_only",
    }
    if contract["threading"] != expected_threading:
        raise AndroidFacadeContractViolation("unexpected threading policy")
    return contract


def execute_fixture(contract: dict[str, Any], fixture: object) -> dict[str, Any]:
    """Execute one closed scenario until completion or its first rejection."""
    if not isinstance(fixture, dict) or set(fixture) != FIXTURE_FIELDS:
        raise AndroidFacadeContractViolation("invalid fixture fields")
    if fixture["contract_version"] != contract["contract_version"]:
        raise AndroidFacadeContractViolation("unsupported fixture version")
    if not isinstance(fixture["name"], str) or not fixture["name"]:
        raise AndroidFacadeContractViolation("fixture name must be non-empty")
    if not isinstance(fixture["actions"], list) or not fixture["actions"]:
        raise AndroidFacadeContractViolation("actions must be non-empty")
    if not isinstance(fixture["expected"], dict) or set(fixture["expected"]) != EXPECTED_FIELDS:
        raise AndroidFacadeContractViolation("invalid expected fields")

    model = FacadeState()
    effects = []
    error = None
    for action in fixture["actions"]:
        if not isinstance(action, dict) or action.get("type") not in contract["actions"]:
            raise AndroidFacadeContractViolation("unknown action")
        try:
            effect = apply_action(model, action)
        except AndroidFacadeViolation as violation:
            if violation.code not in contract["errors"]:
                raise AndroidFacadeContractViolation("unregistered error") from violation
            error = violation.code
            break
        if effect["type"] not in contract["effects"]:
            raise AndroidFacadeContractViolation("unregistered effect")
        effects.append(effect)
    return {"final_state": model.snapshot(), "effects": effects, "error": error}


def main() -> int:
    """Execute all reviewed facade fixtures."""
    contract = load_contract()
    paths = sorted(CONTRACT_DIRECTORY.glob("[0-9][0-9]-*.json"))
    failures = []
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        actual = execute_fixture(contract, fixture)
        if actual != fixture["expected"]:
            failures.append(path.name)
            print(f"FAIL {path.name}", file=sys.stderr)
            print(
                json.dumps({"expected": fixture["expected"], "actual": actual}, indent=2),
                file=sys.stderr,
            )
        else:
            print(f"PASS {path.name}")
    if failures:
        print(f"{len(failures)} Android facade fixture(s) failed.", file=sys.stderr)
        return 1
    print(f"All {len(paths)} Android facade fixtures passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
