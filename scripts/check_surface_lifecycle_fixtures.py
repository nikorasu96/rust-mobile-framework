#!/usr/bin/env python3
"""Execute surface lifecycle and generational-handle fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.surface_lifecycle_model import (
        MAX_U64,
        SurfaceLifecycleViolation,
        transition,
        validate_handle,
        validate_state,
    )
except ModuleNotFoundError:
    from surface_lifecycle_model import (
        MAX_U64,
        SurfaceLifecycleViolation,
        transition,
        validate_handle,
        validate_state,
    )

FIXTURE_FIELDS = {"contract_version", "name", "initial", "actions", "expected"}


def validate_fixture(fixture: object) -> None:
    """Validate a closed fixture envelope and all of its actions."""
    if not isinstance(fixture, dict) or set(fixture) != FIXTURE_FIELDS:
        raise SurfaceLifecycleViolation("invalid fixture fields")
    if fixture["contract_version"] != 1:
        raise SurfaceLifecycleViolation("unsupported contract version")
    if not isinstance(fixture["name"], str) or not fixture["name"]:
        raise SurfaceLifecycleViolation("fixture name must be non-empty")
    validate_state(fixture["initial"])
    if not isinstance(fixture["actions"], list) or not fixture["actions"]:
        raise SurfaceLifecycleViolation("actions must be a non-empty list")
    if not isinstance(fixture["expected"], dict):
        raise SurfaceLifecycleViolation("expected must be an object")


def execute(fixture: dict[str, Any]) -> dict[str, Any]:
    """Execute one lifecycle fixture and return every outcome plus final state."""
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
    directory = root / "contracts" / "surface-lifecycle" / "v1"
    failures = []
    fixtures = sorted(directory.glob("*.json"))
    for path in fixtures:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        try:
            actual = execute(fixture)
        except SurfaceLifecycleViolation as error:
            actual = {"contract_error": str(error)}
        if actual != fixture["expected"]:
            failures.append(path.name)
            print(f"FAIL {path.name}", file=sys.stderr)
            print(json.dumps({"expected": fixture["expected"], "actual": actual}, indent=2), file=sys.stderr)
        else:
            print(f"PASS {path.name}")
    if failures:
        print(f"{len(failures)} surface lifecycle fixture(s) failed.", file=sys.stderr)
        return 1
    print(f"All {len(fixtures)} surface lifecycle fixtures passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
