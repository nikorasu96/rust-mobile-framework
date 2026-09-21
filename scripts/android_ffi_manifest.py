"""Closed machine-readable Android FFI v1 registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIRECTORY = ROOT / "contracts" / "android-ffi" / "v1"
MANIFEST_FIELDS = {
    "contract_version",
    "jni_method",
    "response_frame",
    "operation_payload_frame",
    "event_body",
    "commit_result_body",
    "decoder_errors",
    "limits",
    "operations",
    "status_codes",
}
EXPECTED_METHOD = {
    "class": "dev.rmf.android.NativeBridge",
    "name": "nativeDispatch",
    "descriptor": "(IIJJJ[B)[B",
    "registration": "RegisterNatives",
}
EXPECTED_RESPONSE_FRAME = {
    "magic_hex": "524d4631",
    "endianness": "little",
    "header_bytes": 32,
    "layout": [
        "magic:u8[4]",
        "abi_version:u16",
        "header_bytes:u16",
        "status:i32",
        "payload_bytes:u32",
        "request_id:i64",
        "reserved:u8[8]",
    ],
}
EXPECTED_OPERATION_PAYLOAD_FRAME = {
    "magic_hex": "524d5031",
    "endianness": "little",
    "header_bytes": 16,
    "schema_version": 1,
    "layout": [
        "magic:u8[4]",
        "schema_version:u16",
        "operation:u16",
        "body_bytes:u32",
        "reserved:u8[4]",
    ],
}
EXPECTED_EVENT_BODY = {
    "bytes": 24,
    "layout": ["node_id:i64", "event_code:u16", "flags:u16", "sequence:i64", "reserved:u32"],
    "event_codes": {"CLICK": 1},
}
EXPECTED_COMMIT_RESULT_BODY = {
    "bytes": 24,
    "layout": [
        "base_revision:i64",
        "target_revision:i64",
        "outcome:u16",
        "reason:u16",
        "flags:u32",
    ],
    "outcomes": {"APPLIED": 1, "REJECTED_BEFORE_MUTATION": 2, "FAILED_AFTER_MUTATION": 3},
    "reasons": {"NONE": 0, "HOST_VALIDATION": 1, "HOST_UNAVAILABLE": 2, "HOST_INTERNAL": 3},
}
EXPECTED_DECODER_ERRORS = [
    "TRUNCATED_HEADER",
    "INVALID_MAGIC",
    "UNSUPPORTED_ABI",
    "INVALID_HEADER_LENGTH",
    "UNKNOWN_STATUS",
    "INVALID_REQUEST_ID",
    "NONZERO_RESERVED",
    "PAYLOAD_TOO_LARGE",
    "PAYLOAD_LENGTH_MISMATCH",
    "TRUNCATED_PAYLOAD_HEADER",
    "INVALID_PAYLOAD_MAGIC",
    "UNSUPPORTED_PAYLOAD_VERSION",
    "PAYLOAD_OPERATION_MISMATCH",
    "NONZERO_PAYLOAD_RESERVED",
    "EMPTY_PAYLOAD_BODY",
    "INVALID_BODY_LENGTH",
    "INVALID_NODE_ID",
    "UNKNOWN_EVENT_CODE",
    "INVALID_EVENT_SEQUENCE",
    "NONZERO_BODY_FLAGS",
    "NONZERO_BODY_RESERVED",
    "INVALID_REVISION",
    "UNKNOWN_COMMIT_OUTCOME",
    "UNKNOWN_COMMIT_REASON",
    "INVALID_OUTCOME_REASON",
]
EXPECTED_OPERATIONS = {
    "CREATE_SURFACE": 1,
    "DISPOSE_SURFACE": 2,
    "DISPATCH_EVENT": 3,
    "REPORT_COMMIT_RESULT": 4,
}
EXPECTED_STATUSES = {
    "OK": 0,
    "UNSUPPORTED_ABI": 100,
    "UNKNOWN_OPERATION": 101,
    "INVALID_ARGUMENT": 102,
    "WRONG_THREAD": 103,
    "PAYLOAD_TOO_LARGE": 104,
    "INTERNAL_PANIC": 900,
}


class AndroidFfiContractViolation(Exception):
    """Raised when the manifest is outside the closed v1 contract."""


def load_contract(path: Path = CONTRACT_DIRECTORY / "contract.json") -> dict[str, Any]:
    """Load and validate every registry that affects the FFI wire contract."""
    contract = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict) or set(contract) != MANIFEST_FIELDS:
        raise AndroidFfiContractViolation("invalid contract fields")
    if contract["contract_version"] != 1:
        raise AndroidFfiContractViolation("unsupported contract version")
    expected_sections = {
        "jni_method": (EXPECTED_METHOD, "JNI method"),
        "response_frame": (EXPECTED_RESPONSE_FRAME, "response frame"),
        "operation_payload_frame": (EXPECTED_OPERATION_PAYLOAD_FRAME, "operation payload"),
        "event_body": (EXPECTED_EVENT_BODY, "event body"),
        "commit_result_body": (EXPECTED_COMMIT_RESULT_BODY, "commit result body"),
        "decoder_errors": (EXPECTED_DECODER_ERRORS, "decoder error registry"),
        "operations": (EXPECTED_OPERATIONS, "operation registry"),
        "status_codes": (EXPECTED_STATUSES, "status registry"),
    }
    for key, (expected, label) in expected_sections.items():
        if contract[key] != expected:
            raise AndroidFfiContractViolation(f"unexpected {label} contract")
    expected_limits = {"max_payload_bytes": 1_048_576, "max_transport_id": 2**63 - 1}
    if contract["limits"] != expected_limits:
        raise AndroidFfiContractViolation("unexpected transport limits")
    return contract
