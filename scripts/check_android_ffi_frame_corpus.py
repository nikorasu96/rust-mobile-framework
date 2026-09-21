#!/usr/bin/env python3
"""Execute the reviewed Android FFI binary-frame corruption corpus."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.android_ffi_frames import (
        AndroidFfiFrameViolation,
        decode_operation_payload,
        decode_response_frame,
    )
    from scripts.check_android_ffi_fixtures import load_contract
except ModuleNotFoundError:
    from android_ffi_frames import (
        AndroidFfiFrameViolation,
        decode_operation_payload,
        decode_response_frame,
    )
    from check_android_ffi_fixtures import load_contract


ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIRECTORY = ROOT / "contracts" / "android-ffi" / "v1" / "corpus"
CORPUS_FIELDS = {"contract_version", "kind", "cases"}
RESPONSE_CASE_FIELDS = {"name", "frame_hex", "expected"}
PAYLOAD_CASE_FIELDS = {"name", "operation", "frame_hex", "expected"}
HEX_PATTERN = re.compile(r"[0-9a-f]*\Z")


class AndroidFfiCorpusViolation(Exception):
    """Raised when corpus metadata is not closed and reproducible."""


def _decode_hex(value: object) -> bytes:
    if not isinstance(value, str) or len(value) % 2 or not HEX_PATTERN.fullmatch(value):
        raise AndroidFfiCorpusViolation("frame_hex must be canonical lowercase hexadecimal")
    return bytes.fromhex(value)


def _validate_case(value: object, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AndroidFfiCorpusViolation("invalid corpus case fields")
    if not isinstance(value["name"], str) or not value["name"]:
        raise AndroidFfiCorpusViolation("corpus case name must be non-empty")
    _decode_hex(value["frame_hex"])
    if not isinstance(value["expected"], dict):
        raise AndroidFfiCorpusViolation("expected must be an object")
    return value


def _execute(decoder: Callable[[], dict[str, Any]], result_key: str) -> dict[str, Any]:
    try:
        return {"result": "accepted", result_key: decoder()}
    except AndroidFfiFrameViolation as error:
        return {"result": "rejected", "code": error.code}


def execute_corpus(path: Path, contract: dict[str, Any]) -> tuple[int, list[str]]:
    """Execute one closed corpus file and return count plus failure names."""
    corpus = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(corpus, dict) or set(corpus) != CORPUS_FIELDS:
        raise AndroidFfiCorpusViolation("invalid corpus fields")
    if corpus["contract_version"] != contract["contract_version"]:
        raise AndroidFfiCorpusViolation("unsupported corpus version")
    if corpus["kind"] not in {"response_frame", "operation_payload"}:
        raise AndroidFfiCorpusViolation("unknown corpus kind")
    if not isinstance(corpus["cases"], list) or not corpus["cases"]:
        raise AndroidFfiCorpusViolation("cases must be a non-empty list")

    failures = []
    for raw_case in corpus["cases"]:
        fields = RESPONSE_CASE_FIELDS if corpus["kind"] == "response_frame" else PAYLOAD_CASE_FIELDS
        case = _validate_case(raw_case, fields)
        data = _decode_hex(case["frame_hex"])
        if corpus["kind"] == "response_frame":
            actual = _execute(lambda: decode_response_frame(contract, data), "frame")
        else:
            operation = case["operation"]
            if not isinstance(operation, int) or isinstance(operation, bool):
                raise AndroidFfiCorpusViolation("operation must be an integer")
            actual = _execute(
                lambda: decode_operation_payload(contract, operation, data),
                "payload",
            )
        if actual != case["expected"]:
            failures.append(case["name"])
            print(f"FAIL {path.name}:{case['name']}", file=sys.stderr)
        else:
            print(f"PASS {path.name}:{case['name']}")
    return len(corpus["cases"]), failures


def main() -> int:
    """Execute every checked-in corruption corpus."""
    contract = load_contract()
    total = 0
    failures = []
    for name in ("operation-payloads.json", "response-frames.json"):
        path = CORPUS_DIRECTORY / name
        count, corpus_failures = execute_corpus(path, contract)
        total += count
        failures.extend(corpus_failures)
    if failures:
        print(f"{len(failures)} Android FFI frame case(s) failed.", file=sys.stderr)
        return 1
    print(f"All {total} Android FFI frame cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
