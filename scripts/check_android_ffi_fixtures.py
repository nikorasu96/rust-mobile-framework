#!/usr/bin/env python3
"""Validate the closed Android JNI admission contract and reviewed fixtures."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

try:
    from scripts.android_ffi_bodies import decode_commit_result_body, decode_event_body
    from scripts.android_ffi_frames import AndroidFfiFrameViolation, decode_operation_payload
    from scripts.android_ffi_manifest import (
        AndroidFfiContractViolation,
        CONTRACT_DIRECTORY,
        load_contract,
    )
except ModuleNotFoundError:
    from android_ffi_bodies import decode_commit_result_body, decode_event_body
    from android_ffi_frames import AndroidFfiFrameViolation, decode_operation_payload
    from android_ffi_manifest import AndroidFfiContractViolation, CONTRACT_DIRECTORY, load_contract


FIXTURE_FIELDS = {"contract_version", "name", "input", "expected"}
INPUT_FIELDS = {
    "abi_version",
    "operation",
    "request_id",
    "surface_id",
    "generation",
    "payload_hex",
    "caller_thread",
}
EMPTY_PAYLOAD_OPERATIONS = {"CREATE_SURFACE", "DISPOSE_SURFACE"}
NONEMPTY_PAYLOAD_OPERATIONS = {"DISPATCH_EVENT", "REPORT_COMMIT_RESULT"}
HEX_PATTERN = re.compile(r"[0-9a-f]*\Z")


def _closed_object(value: object, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AndroidFfiContractViolation(f"invalid {name} fields")
    return value


def _rejected(contract: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "result": "rejected",
        "status": contract["status_codes"][code],
        "code": code,
    }


def _transport_id(value: object, maximum: int) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= maximum:
        return None
    return value


def admit(contract: dict[str, Any], value: object) -> dict[str, Any]:
    """Apply deterministic pre-runtime JNI admission and normalize owned values."""
    if not isinstance(value, dict) or set(value) != INPUT_FIELDS:
        return _rejected(contract, "INVALID_ARGUMENT")
    abi_version = value["abi_version"]
    if not isinstance(abi_version, int) or isinstance(abi_version, bool):
        return _rejected(contract, "INVALID_ARGUMENT")
    if abi_version != contract["contract_version"]:
        return _rejected(contract, "UNSUPPORTED_ABI")
    if value["caller_thread"] != "main":
        return _rejected(contract, "WRONG_THREAD")

    operation_code = value["operation"]
    if not isinstance(operation_code, int) or isinstance(operation_code, bool):
        return _rejected(contract, "UNKNOWN_OPERATION")
    names_by_code = {code: name for name, code in contract["operations"].items()}
    operation = names_by_code.get(operation_code)
    if operation is None:
        return _rejected(contract, "UNKNOWN_OPERATION")

    maximum = contract["limits"]["max_transport_id"]
    request_id = _transport_id(value["request_id"], maximum)
    surface_id = _transport_id(value["surface_id"], maximum)
    generation = value["generation"]
    if request_id is None or surface_id is None:
        return _rejected(contract, "INVALID_ARGUMENT")
    if operation == "CREATE_SURFACE":
        if generation != 0 or isinstance(generation, bool):
            return _rejected(contract, "INVALID_ARGUMENT")
        normalized_generation = None
    else:
        normalized_generation = _transport_id(generation, maximum)
        if normalized_generation is None:
            return _rejected(contract, "INVALID_ARGUMENT")

    payload_hex = value["payload_hex"]
    if not isinstance(payload_hex, str) or len(payload_hex) % 2 or not HEX_PATTERN.fullmatch(payload_hex):
        return _rejected(contract, "INVALID_ARGUMENT")
    payload_bytes = len(payload_hex) // 2
    if payload_bytes > contract["limits"]["max_payload_bytes"]:
        return _rejected(contract, "PAYLOAD_TOO_LARGE")
    if operation in EMPTY_PAYLOAD_OPERATIONS and payload_bytes != 0:
        return _rejected(contract, "INVALID_ARGUMENT")
    if operation in NONEMPTY_PAYLOAD_OPERATIONS and payload_bytes == 0:
        return _rejected(contract, "INVALID_ARGUMENT")
    typed_payload = None
    if operation in NONEMPTY_PAYLOAD_OPERATIONS:
        try:
            decoded = decode_operation_payload(contract, operation_code, bytes.fromhex(payload_hex))
            body = bytes.fromhex(decoded["body_hex"])
            if operation == "DISPATCH_EVENT":
                typed_payload = decode_event_body(contract, body)
            else:
                typed_payload = decode_commit_result_body(contract, body)
        except AndroidFfiFrameViolation:
            return _rejected(contract, "INVALID_ARGUMENT")

    request = {
        "operation": operation,
        "request_id": request_id,
        "surface_id": surface_id,
        "generation": normalized_generation,
        "payload_bytes": payload_bytes,
    }
    if typed_payload is not None:
        request["payload"] = typed_payload
    return {
        "result": "accepted",
        "status": contract["status_codes"]["OK"],
        "code": "OK",
        "request": request,
    }


def validate_fixture(value: object) -> dict[str, Any]:
    """Validate and return one closed fixture envelope."""
    fixture = _closed_object(value, FIXTURE_FIELDS, "fixture")
    if fixture["contract_version"] != 1:
        raise AndroidFfiContractViolation("unsupported fixture contract version")
    if not isinstance(fixture["name"], str) or not fixture["name"]:
        raise AndroidFfiContractViolation("fixture name must be non-empty")
    _closed_object(fixture["input"], INPUT_FIELDS, "input")
    if not isinstance(fixture["expected"], dict):
        raise AndroidFfiContractViolation("expected must be an object")
    return fixture


def main() -> int:
    """Execute every reviewed v1 fixture against the admission model."""
    contract = load_contract()
    failures = []
    fixtures = sorted(CONTRACT_DIRECTORY.glob("[0-9][0-9]-*.json"))
    for path in fixtures:
        fixture = validate_fixture(json.loads(path.read_text(encoding="utf-8")))
        actual = admit(contract, fixture["input"])
        if actual != fixture["expected"]:
            failures.append(path.name)
            print(f"FAIL {path.name}", file=sys.stderr)
            print(json.dumps({"expected": fixture["expected"], "actual": actual}, indent=2), file=sys.stderr)
        else:
            print(f"PASS {path.name}")
    if failures:
        print(f"{len(failures)} Android FFI fixture(s) failed.", file=sys.stderr)
        return 1
    print(f"All {len(fixtures)} Android FFI fixtures passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
