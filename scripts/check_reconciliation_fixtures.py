#!/usr/bin/env python3
"""Execute the language-independent reconciliation v1 golden fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__:
    from .reconciliation_batch_model import BatchApplicationError, verify_batch_result
    from .reconciliation_oracle import execute
    from .reconciliation_validation import ContractViolation, load_component_schemas
else:
    from reconciliation_batch_model import BatchApplicationError, verify_batch_result
    from reconciliation_oracle import execute
    from reconciliation_validation import ContractViolation, load_component_schemas


def main() -> int:
    """Execute every version-one fixture and compare its exact expected result."""
    root = Path(__file__).resolve().parents[1]
    fixture_directory = root / "contracts" / "reconciliation" / "v1"
    try:
        schemas = load_component_schemas(fixture_directory / "schema" / "components.json")
    except ContractViolation as error:
        print(f"FAIL component schema: {error.code}: {error}", file=sys.stderr)
        return 1

    failures = []
    fixtures = sorted(fixture_directory.glob("*.json"))
    for path in fixtures:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        try:
            actual = execute(fixture, schemas)
            if actual.get("result") == "batch":
                verify_batch_result(fixture["previous"], actual)
        except ContractViolation as error:
            actual = {"result": "error", "code": error.code}
        except BatchApplicationError as error:
            actual = {"result": "model_error", "detail": str(error)}
        if actual != fixture["expected"]:
            failures.append(path.name)
            print(f"FAIL {path.name}", file=sys.stderr)
            print(json.dumps({"expected": fixture["expected"], "actual": actual}, indent=2), file=sys.stderr)
        else:
            print(f"PASS {path.name}")
    if failures:
        print(f"{len(failures)} reconciliation fixture(s) failed.", file=sys.stderr)
        return 1
    print(f"All {len(fixtures)} reconciliation fixtures passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
