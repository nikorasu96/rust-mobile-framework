"""Strict codecs for Android FFI v1 response and operation-payload frames."""

from __future__ import annotations

import struct
from typing import Any


RESPONSE_HEADER = struct.Struct("<4sHHiIq8s")
PAYLOAD_HEADER = struct.Struct("<4sHHI4s")


class AndroidFfiFrameViolation(Exception):
    """Raised with a stable code when a binary FFI frame is malformed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _violation(contract: dict[str, Any], code: str) -> AndroidFfiFrameViolation:
    if code not in contract["decoder_errors"]:
        raise ValueError(f"unregistered decoder error: {code}")
    return AndroidFfiFrameViolation(code)


def encode_response_frame(
    contract: dict[str, Any], status: int, request_id: int, payload: bytes = b""
) -> bytes:
    """Encode one owned response using the fixed v1 byte layout."""
    if status not in contract["status_codes"].values():
        raise AndroidFfiFrameViolation("UNKNOWN_STATUS")
    maximum = contract["limits"]["max_transport_id"]
    if not isinstance(request_id, int) or isinstance(request_id, bool) or not 0 <= request_id <= maximum:
        raise AndroidFfiFrameViolation("INVALID_REQUEST_ID")
    if not isinstance(payload, bytes) or len(payload) > contract["limits"]["max_payload_bytes"]:
        raise AndroidFfiFrameViolation("PAYLOAD_TOO_LARGE")
    frame = contract["response_frame"]
    header = RESPONSE_HEADER.pack(
        bytes.fromhex(frame["magic_hex"]),
        contract["contract_version"],
        frame["header_bytes"],
        status,
        len(payload),
        request_id,
        bytes(8),
    )
    return header + payload


def decode_response_frame(contract: dict[str, Any], data: bytes) -> dict[str, Any]:
    """Decode a complete response only after validating every header invariant."""
    frame = contract["response_frame"]
    if len(data) < frame["header_bytes"]:
        raise _violation(contract, "TRUNCATED_HEADER")
    magic, abi, header_bytes, status, payload_bytes, request_id, reserved = RESPONSE_HEADER.unpack_from(data)
    if magic != bytes.fromhex(frame["magic_hex"]):
        raise _violation(contract, "INVALID_MAGIC")
    if abi != contract["contract_version"]:
        raise _violation(contract, "UNSUPPORTED_ABI")
    if header_bytes != frame["header_bytes"]:
        raise _violation(contract, "INVALID_HEADER_LENGTH")
    if status not in contract["status_codes"].values():
        raise _violation(contract, "UNKNOWN_STATUS")
    if not 0 <= request_id <= contract["limits"]["max_transport_id"]:
        raise _violation(contract, "INVALID_REQUEST_ID")
    if reserved != bytes(8):
        raise _violation(contract, "NONZERO_RESERVED")
    if payload_bytes > contract["limits"]["max_payload_bytes"]:
        raise _violation(contract, "PAYLOAD_TOO_LARGE")
    if len(data) != header_bytes + payload_bytes:
        raise _violation(contract, "PAYLOAD_LENGTH_MISMATCH")
    return {
        "abi_version": abi,
        "status": status,
        "request_id": request_id,
        "payload_hex": data[header_bytes:].hex(),
    }


def encode_operation_payload(contract: dict[str, Any], operation: int, body: bytes) -> bytes:
    """Encode one event or commit-result payload with its operation discriminator."""
    valid_operations = {
        contract["operations"]["DISPATCH_EVENT"],
        contract["operations"]["REPORT_COMMIT_RESULT"],
    }
    if operation not in valid_operations or not isinstance(operation, int) or isinstance(operation, bool):
        raise AndroidFfiFrameViolation("PAYLOAD_OPERATION_MISMATCH")
    frame = contract["operation_payload_frame"]
    maximum_body = contract["limits"]["max_payload_bytes"] - frame["header_bytes"]
    if not isinstance(body, bytes) or not body or len(body) > maximum_body:
        raise AndroidFfiFrameViolation("PAYLOAD_TOO_LARGE")
    header = PAYLOAD_HEADER.pack(
        bytes.fromhex(frame["magic_hex"]),
        frame["schema_version"],
        operation,
        len(body),
        bytes(4),
    )
    return header + body


def decode_operation_payload(
    contract: dict[str, Any], expected_operation: int, data: bytes
) -> dict[str, Any]:
    """Decode a complete operation payload after closed header validation."""
    frame = contract["operation_payload_frame"]
    if len(data) < frame["header_bytes"]:
        raise _violation(contract, "TRUNCATED_PAYLOAD_HEADER")
    magic, version, operation, body_bytes, reserved = PAYLOAD_HEADER.unpack_from(data)
    if magic != bytes.fromhex(frame["magic_hex"]):
        raise _violation(contract, "INVALID_PAYLOAD_MAGIC")
    if version != frame["schema_version"]:
        raise _violation(contract, "UNSUPPORTED_PAYLOAD_VERSION")
    if operation != expected_operation:
        raise _violation(contract, "PAYLOAD_OPERATION_MISMATCH")
    if reserved != bytes(4):
        raise _violation(contract, "NONZERO_PAYLOAD_RESERVED")
    if body_bytes == 0:
        raise _violation(contract, "EMPTY_PAYLOAD_BODY")
    if body_bytes > contract["limits"]["max_payload_bytes"] - frame["header_bytes"]:
        raise _violation(contract, "PAYLOAD_TOO_LARGE")
    if len(data) != frame["header_bytes"] + body_bytes:
        raise _violation(contract, "PAYLOAD_LENGTH_MISMATCH")
    return {
        "schema_version": version,
        "operation": operation,
        "body_hex": data[frame["header_bytes"] :].hex(),
    }
