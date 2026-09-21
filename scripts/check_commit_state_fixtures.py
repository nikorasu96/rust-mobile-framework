#!/usr/bin/env python3
"""Execute commit-application and recovery state-machine fixtures."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

MAX_REVISION = 2**64 - 1
FIXTURE_FIELDS = {"contract_version", "name", "initial", "actions", "expected"}
STATE_FIELDS = {
    "ready": {"state", "revision"},
    "applying": {"state", "base_revision", "target_revision"},
    "failed": {"state", "revision", "attempted_revision", "failure_code"},
    "remounting": {"state", "revision", "attempted_revision"},
}
ACTION_FIELDS = {
    "begin_apply": {"op", "base_revision", "target_revision"},
    "host_applied": {"op"},
    "host_rejected": {"op", "code"},
    "host_failed": {"op", "code"},
    "begin_remount": {"op"},
    "remount_succeeded": {"op"},
    "remount_failed": {"op", "code"},
}


class CommitContractViolation(Exception):
    """Raised when fixture data is outside the closed v1 contract."""


def _revision(value: object, name: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value > MAX_REVISION
    ):
        raise CommitContractViolation(f"{name} must be a u64 revision")
    return value


def _code(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value) is None:
        raise CommitContractViolation("failure code must be a stable uppercase identifier")
    return value


def validate_state(state: object) -> dict[str, Any]:
    """Validate and copy a closed runtime state object."""
    if not isinstance(state, dict) or state.get("state") not in STATE_FIELDS:
        raise CommitContractViolation("unknown surface state")
    name = state["state"]
    if set(state) != STATE_FIELDS[name]:
        raise CommitContractViolation(f"invalid fields for state {name}")
    if name == "applying":
        base = _revision(state["base_revision"], "base_revision")
        target = _revision(state["target_revision"], "target_revision")
        if base == MAX_REVISION or target != base + 1:
            raise CommitContractViolation("applying revisions must be consecutive")
    else:
        _revision(state["revision"], "revision")
    if name in {"failed", "remounting"}:
        attempted = _revision(state["attempted_revision"], "attempted_revision")
        if state["revision"] == MAX_REVISION or attempted != state["revision"] + 1:
            raise CommitContractViolation("recovery revisions must be consecutive")
    if name == "failed":
        _code(state["failure_code"])
    return copy.deepcopy(state)


def validate_fixture(fixture: object) -> None:
    """Validate fixture and action envelopes before executing transitions."""
    if not isinstance(fixture, dict) or set(fixture) != FIXTURE_FIELDS:
        raise CommitContractViolation("invalid fixture fields")
    if fixture["contract_version"] != 1:
        raise CommitContractViolation("unsupported contract version")
    if not isinstance(fixture["name"], str) or not fixture["name"]:
        raise CommitContractViolation("fixture name must be non-empty")
    validate_state(fixture["initial"])
    if not isinstance(fixture["actions"], list) or not fixture["actions"]:
        raise CommitContractViolation("actions must be a non-empty list")
    if not isinstance(fixture["expected"], dict):
        raise CommitContractViolation("expected must be an object")
    for action in fixture["actions"]:
        if not isinstance(action, dict) or action.get("op") not in ACTION_FIELDS:
            raise CommitContractViolation("unknown action")
        if set(action) != ACTION_FIELDS[action["op"]]:
            raise CommitContractViolation(f"invalid fields for action {action['op']}")
        if action["op"] == "begin_apply":
            _revision(action["base_revision"], "base_revision")
            _revision(action["target_revision"], "target_revision")
        if "code" in action:
            _code(action["code"])


def _rejected(state: dict[str, Any], code: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return state, {"result": "rejected", "code": code}


def transition(
    state: dict[str, Any], action: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one valid action and return the next state plus typed outcome."""
    state_name = state["state"]
    operation = action["op"]
    if operation == "begin_apply":
        if state_name == "failed":
            return _rejected(state, "RECOVERY_REQUIRED")
        if state_name != "ready":
            return _rejected(state, "SURFACE_BUSY")
        base = action["base_revision"]
        target = action["target_revision"]
        if base != state["revision"]:
            return _rejected(state, "STALE_BATCH")
        if base == MAX_REVISION or target != base + 1:
            return _rejected(state, "INVALID_REVISION")
        return (
            {"state": "applying", "base_revision": base, "target_revision": target},
            {"result": "apply_started", "base_revision": base, "target_revision": target},
        )

    if operation == "begin_remount":
        if state_name != "failed":
            return _rejected(state, "INVALID_TRANSITION")
        return (
            {
                "state": "remounting",
                "revision": state["revision"],
                "attempted_revision": state["attempted_revision"],
            },
            {"result": "remount_started", "revision": state["revision"]},
        )

    if state_name == "applying":
        base = state["base_revision"]
        target = state["target_revision"]
        if operation == "host_applied":
            return (
                {"state": "ready", "revision": target},
                {"result": "commit_promoted", "revision": target},
            )
        if operation == "host_rejected":
            return (
                {"state": "ready", "revision": base},
                {"result": "batch_discarded", "code": action["code"], "revision": base},
            )
        if operation == "host_failed":
            return (
                {
                    "state": "failed",
                    "revision": base,
                    "attempted_revision": target,
                    "failure_code": action["code"],
                },
                {"result": "recovery_required", "code": action["code"], "revision": base},
            )

    if state_name == "remounting":
        revision = state["revision"]
        attempted = state["attempted_revision"]
        if operation == "remount_succeeded":
            return (
                {"state": "ready", "revision": revision},
                {"result": "surface_restored", "revision": revision},
            )
        if operation == "remount_failed":
            return (
                {
                    "state": "failed",
                    "revision": revision,
                    "attempted_revision": attempted,
                    "failure_code": action["code"],
                },
                {"result": "recovery_required", "code": action["code"], "revision": revision},
            )

    return _rejected(state, "INVALID_TRANSITION")


def execute(fixture: dict[str, Any]) -> dict[str, Any]:
    """Execute one closed fixture from its initial state."""
    validate_fixture(fixture)
    state = validate_state(fixture["initial"])
    outputs = []
    for action in fixture["actions"]:
        state, output = transition(state, action)
        outputs.append(output)
    return {"outputs": outputs, "final": state}


def main() -> int:
    """Execute every v1 fixture and compare exact expected results."""
    root = Path(__file__).resolve().parents[1]
    fixture_directory = root / "contracts" / "commit-application" / "v1"
    failures = []
    fixtures = sorted(fixture_directory.glob("*.json"))
    for path in fixtures:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        try:
            actual = execute(fixture)
        except CommitContractViolation as error:
            actual = {"contract_error": str(error)}
        if actual != fixture["expected"]:
            failures.append(path.name)
            print(f"FAIL {path.name}", file=sys.stderr)
            print(json.dumps({"expected": fixture["expected"], "actual": actual}, indent=2), file=sys.stderr)
        else:
            print(f"PASS {path.name}")
    if failures:
        print(f"{len(failures)} commit fixture(s) failed.", file=sys.stderr)
        return 1
    print(f"All {len(fixtures)} commit-application fixtures passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
