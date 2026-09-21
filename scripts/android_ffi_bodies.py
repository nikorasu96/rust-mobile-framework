"""Typed Android FFI v1 bodies for events and commit results."""

from __future__ import annotations

import struct
from typing import Any

try:
    from scripts.android_ffi_frames import AndroidFfiFrameViolation
except ModuleNotFoundError:
    from android_ffi_frames import AndroidFfiFrameViolation


EVENT_BODY = struct.Struct("<qHHqI")
COMMIT_RESULT_BODY = struct.Struct("<qqHHI")


def _fail(contract: dict[str, Any], code: str) -> AndroidFfiFrameViolation:
    if code not in contract["decoder_errors"]:
        raise ValueError(f"unregistered decoder error: {code}")
    return AndroidFfiFrameViolation(code)


def _plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def encode_event_body(
    contract: dict[str, Any], node_id: int, event_code: int, sequence: int
) -> bytes:
    """Encode a validated v1 event body with zeroed evolution fields."""
    maximum = contract["limits"]["max_transport_id"]
    if not _plain_int(node_id) or not 0 < node_id <= maximum:
        raise _fail(contract, "INVALID_NODE_ID")
    if not _plain_int(event_code) or event_code not in contract["event_body"]["event_codes"].values():
        raise _fail(contract, "UNKNOWN_EVENT_CODE")
    if not _plain_int(sequence) or not 0 < sequence <= maximum:
        raise _fail(contract, "INVALID_EVENT_SEQUENCE")
    return EVENT_BODY.pack(node_id, event_code, 0, sequence, 0)


def decode_event_body(contract: dict[str, Any], body: bytes) -> dict[str, Any]:
    """Decode a click event only after checking its complete fixed-size body."""
    specification = contract["event_body"]
    if len(body) != specification["bytes"]:
        raise _fail(contract, "INVALID_BODY_LENGTH")
    node_id, event_code, flags, sequence, reserved = EVENT_BODY.unpack(body)
    maximum = contract["limits"]["max_transport_id"]
    if not 0 < node_id <= maximum:
        raise _fail(contract, "INVALID_NODE_ID")
    names_by_code = {code: name for name, code in specification["event_codes"].items()}
    event = names_by_code.get(event_code)
    if event is None:
        raise _fail(contract, "UNKNOWN_EVENT_CODE")
    if flags != 0:
        raise _fail(contract, "NONZERO_BODY_FLAGS")
    if not 0 < sequence <= maximum:
        raise _fail(contract, "INVALID_EVENT_SEQUENCE")
    if reserved != 0:
        raise _fail(contract, "NONZERO_BODY_RESERVED")
    return {"node_id": node_id, "event": event, "sequence": sequence}


def encode_commit_result_body(
    contract: dict[str, Any], base_revision: int, target_revision: int, outcome: int, reason: int
) -> bytes:
    """Encode a validated v1 commit result with no free-form platform error text."""
    if not _plain_int(base_revision) or not _plain_int(target_revision):
        raise _fail(contract, "INVALID_REVISION")
    maximum = contract["limits"]["max_transport_id"]
    if not 0 <= base_revision < maximum or target_revision != base_revision + 1:
        raise _fail(contract, "INVALID_REVISION")
    if (
        not _plain_int(outcome)
        or outcome not in contract["commit_result_body"]["outcomes"].values()
    ):
        raise _fail(contract, "UNKNOWN_COMMIT_OUTCOME")
    if (
        not _plain_int(reason)
        or reason not in contract["commit_result_body"]["reasons"].values()
    ):
        raise _fail(contract, "UNKNOWN_COMMIT_REASON")
    body = COMMIT_RESULT_BODY.pack(base_revision, target_revision, outcome, reason, 0)
    decode_commit_result_body(contract, body)
    return body


def decode_commit_result_body(contract: dict[str, Any], body: bytes) -> dict[str, Any]:
    """Decode revision and host outcome while enforcing ADR-0004 classifications."""
    specification = contract["commit_result_body"]
    if len(body) != specification["bytes"]:
        raise _fail(contract, "INVALID_BODY_LENGTH")
    base, target, outcome_code, reason_code, flags = COMMIT_RESULT_BODY.unpack(body)
    maximum = contract["limits"]["max_transport_id"]
    if not 0 <= base < maximum or target != base + 1:
        raise _fail(contract, "INVALID_REVISION")
    outcomes = {code: name for name, code in specification["outcomes"].items()}
    reasons = {code: name for name, code in specification["reasons"].items()}
    outcome = outcomes.get(outcome_code)
    if outcome is None:
        raise _fail(contract, "UNKNOWN_COMMIT_OUTCOME")
    reason = reasons.get(reason_code)
    if reason is None:
        raise _fail(contract, "UNKNOWN_COMMIT_REASON")
    if flags != 0:
        raise _fail(contract, "NONZERO_BODY_FLAGS")
    allowed_reasons = {
        "APPLIED": {"NONE"},
        "REJECTED_BEFORE_MUTATION": {"HOST_VALIDATION"},
        "FAILED_AFTER_MUTATION": {"HOST_UNAVAILABLE", "HOST_INTERNAL"},
    }
    if reason not in allowed_reasons[outcome]:
        raise _fail(contract, "INVALID_OUTCOME_REASON")
    return {
        "base_revision": base,
        "target_revision": target,
        "outcome": outcome,
        "reason": reason,
    }
