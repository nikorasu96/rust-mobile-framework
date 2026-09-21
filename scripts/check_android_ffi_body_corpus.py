#!/usr/bin/env python3
"""Execute reviewed Android FFI typed-body boundary cases."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.android_ffi_bodies import decode_commit_result_body, decode_event_body
    from scripts.android_ffi_frames import AndroidFfiFrameViolation
    from scripts.android_ffi_manifest import load_contract
except ModuleNotFoundError:
    from android_ffi_bodies import decode_commit_result_body, decode_event_body
    from android_ffi_frames import AndroidFfiFrameViolation
    from android_ffi_manifest import load_contract


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "contracts" / "android-ffi" / "v1" / "corpus" / "typed-bodies.json"
CORPUS_FIELDS = {"contract_version", "kind", "cases"}
CASE_FIELDS = {"name", "body_kind", "body_hex", "expected"}
HEX_PATTERN = re.compile(r"[0-9a-f]*\Z")


class AndroidFfiBodyCorpusViolation(Exception):
    """Raised when typed-body corpus metadata is not closed."""


def _body(value: object) -> bytes:
    if not isinstance(value, str) or len(value) % 2 or not HEX_PATTERN.fullmatch(value):
        raise AndroidFfiBodyCorpusViolation("body_hex must be canonical lowercase hexadecimal")
    return bytes.fromhex(value)


def _execute(decoder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return {"result": "accepted", "body": decoder()}
    except AndroidFfiFrameViolation as error:
        return {"result": "rejected", "code": error.code}


def execute_corpus(
    path: Path = CORPUS_PATH, contract: dict[str, Any] | None = None
) -> tuple[int, list[str]]:
    """Execute all closed typed-body cases and return count plus failures."""
    active_contract = load_contract() if contract is None else contract
    corpus = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(corpus, dict) or set(corpus) != CORPUS_FIELDS:
        raise AndroidFfiBodyCorpusViolation("invalid corpus fields")
    if corpus["contract_version"] != active_contract["contract_version"]:
        raise AndroidFfiBodyCorpusViolation("unsupported corpus version")
    if corpus["kind"] != "typed_body":
        raise AndroidFfiBodyCorpusViolation("unknown corpus kind")
    if not isinstance(corpus["cases"], list) or not corpus["cases"]:
        raise AndroidFfiBodyCorpusViolation("cases must be a non-empty list")

    failures = []
    for raw_case in corpus["cases"]:
        if not isinstance(raw_case, dict) or set(raw_case) != CASE_FIELDS:
            raise AndroidFfiBodyCorpusViolation("invalid case fields")
        if not isinstance(raw_case["name"], str) or not raw_case["name"]:
            raise AndroidFfiBodyCorpusViolation("case name must be non-empty")
        data = _body(raw_case["body_hex"])
        if raw_case["body_kind"] == "event":
            actual = _execute(lambda: decode_event_body(active_contract, data))
        elif raw_case["body_kind"] == "commit_result":
            actual = _execute(lambda: decode_commit_result_body(active_contract, data))
        else:
            raise AndroidFfiBodyCorpusViolation("unknown body kind")
        if actual != raw_case["expected"]:
            failures.append(raw_case["name"])
            print(f"FAIL {raw_case['name']}", file=sys.stderr)
        else:
            print(f"PASS {raw_case['name']}")
    return len(corpus["cases"]), failures


def main() -> int:
    """Run the complete typed-body corpus."""
    count, failures = execute_corpus()
    if failures:
        print(f"{len(failures)} Android FFI body case(s) failed.", file=sys.stderr)
        return 1
    print(f"All {count} Android FFI typed-body cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
