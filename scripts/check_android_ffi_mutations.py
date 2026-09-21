#!/usr/bin/env python3
"""Exhaustively classify single-bit mutations of canonical Android FFI packets."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.android_ffi_bodies import (
        decode_commit_result_body,
        decode_event_body,
        encode_commit_result_body,
        encode_event_body,
    )
    from scripts.android_ffi_frames import (
        AndroidFfiFrameViolation,
        decode_operation_payload,
        decode_response_frame,
        encode_operation_payload,
        encode_response_frame,
    )
    from scripts.android_ffi_manifest import load_contract
except ModuleNotFoundError:
    from android_ffi_bodies import (
        decode_commit_result_body,
        decode_event_body,
        encode_commit_result_body,
        encode_event_body,
    )
    from android_ffi_frames import (
        AndroidFfiFrameViolation,
        decode_operation_payload,
        decode_response_frame,
        encode_operation_payload,
        encode_response_frame,
    )
    from android_ffi_manifest import load_contract


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_PATH = ROOT / "contracts" / "android-ffi" / "v1" / "mutation-campaign.json"
CAMPAIGN_FIELDS = {"contract_version", "mutation", "bit_masks", "seeds"}
RESPONSE_FIELDS = {"name", "kind", "status", "request_id", "payload_hex"}
EVENT_FIELDS = {"name", "kind", "node_id", "event", "sequence"}
COMMIT_FIELDS = {
    "name",
    "kind",
    "base_revision",
    "target_revision",
    "outcome",
    "reason",
}
HEX_PATTERN = re.compile(r"[0-9a-f]*\Z")


class AndroidFfiMutationViolation(Exception):
    """Raised when campaign metadata or canonical re-encoding is invalid."""


def _registry_code(registry: dict[str, int], name: object, label: str) -> int:
    if not isinstance(name, str) or name not in registry:
        raise AndroidFfiMutationViolation(f"unknown {label}")
    return registry[name]


def _build_seed(contract: dict[str, Any], seed: object) -> tuple[str, int | None, bytes]:
    if (
        not isinstance(seed, dict)
        or not isinstance(seed.get("name"), str)
        or not seed["name"]
    ):
        raise AndroidFfiMutationViolation("invalid seed")
    kind = seed.get("kind")
    if kind == "response" and set(seed) == RESPONSE_FIELDS:
        status = _registry_code(contract["status_codes"], seed["status"], "status")
        if not isinstance(seed["payload_hex"], str) or not HEX_PATTERN.fullmatch(
            seed["payload_hex"]
        ):
            raise AndroidFfiMutationViolation("invalid response payload")
        try:
            payload = bytes.fromhex(seed["payload_hex"])
        except (TypeError, ValueError) as error:
            raise AndroidFfiMutationViolation("invalid response payload") from error
        return kind, None, encode_response_frame(contract, status, seed["request_id"], payload)
    if kind == "event" and set(seed) == EVENT_FIELDS:
        operation = contract["operations"]["DISPATCH_EVENT"]
        event = _registry_code(contract["event_body"]["event_codes"], seed["event"], "event")
        body = encode_event_body(contract, seed["node_id"], event, seed["sequence"])
        return kind, operation, encode_operation_payload(contract, operation, body)
    if kind == "commit_result" and set(seed) == COMMIT_FIELDS:
        operation = contract["operations"]["REPORT_COMMIT_RESULT"]
        outcome = _registry_code(
            contract["commit_result_body"]["outcomes"], seed["outcome"], "outcome"
        )
        reason = _registry_code(
            contract["commit_result_body"]["reasons"], seed["reason"], "reason"
        )
        body = encode_commit_result_body(
            contract, seed["base_revision"], seed["target_revision"], outcome, reason
        )
        return kind, operation, encode_operation_payload(contract, operation, body)
    raise AndroidFfiMutationViolation("invalid seed fields")


def _decode_canonical(
    contract: dict[str, Any], kind: str, operation: int | None, packet: bytes
) -> dict[str, Any]:
    if kind == "response":
        decoded = decode_response_frame(contract, packet)
        rebuilt = encode_response_frame(
            contract,
            decoded["status"],
            decoded["request_id"],
            bytes.fromhex(decoded["payload_hex"]),
        )
        normalized = decoded
    else:
        if operation is None:
            raise AndroidFfiMutationViolation("missing operation")
        outer = decode_operation_payload(contract, operation, packet)
        body = bytes.fromhex(outer["body_hex"])
        if kind == "event":
            normalized = decode_event_body(contract, body)
            event = contract["event_body"]["event_codes"][normalized["event"]]
            rebuilt_body = encode_event_body(
                contract, normalized["node_id"], event, normalized["sequence"]
            )
        else:
            normalized = decode_commit_result_body(contract, body)
            outcomes = contract["commit_result_body"]["outcomes"]
            reasons = contract["commit_result_body"]["reasons"]
            rebuilt_body = encode_commit_result_body(
                contract,
                normalized["base_revision"],
                normalized["target_revision"],
                outcomes[normalized["outcome"]],
                reasons[normalized["reason"]],
            )
        rebuilt = encode_operation_payload(contract, operation, rebuilt_body)
    if rebuilt != packet:
        raise AndroidFfiMutationViolation("accepted mutation is not canonical")
    return normalized


def run_campaign(path: Path = CAMPAIGN_PATH) -> dict[str, Any]:
    """Classify every one-bit mutation and return reproducible aggregate evidence."""
    contract = load_contract()
    campaign = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(campaign, dict) or set(campaign) != CAMPAIGN_FIELDS:
        raise AndroidFfiMutationViolation("invalid campaign fields")
    if campaign["contract_version"] != contract["contract_version"]:
        raise AndroidFfiMutationViolation("unsupported campaign version")
    if campaign["mutation"] != "single_bit" or campaign["bit_masks"] != [
        1,
        2,
        4,
        8,
        16,
        32,
        64,
        128,
    ]:
        raise AndroidFfiMutationViolation("invalid mutation strategy")
    if not isinstance(campaign["seeds"], list) or not campaign["seeds"]:
        raise AndroidFfiMutationViolation("seeds must be non-empty")

    digest = hashlib.sha256()
    outcomes: Counter[str] = Counter()
    rejection_codes: Counter[str] = Counter()
    seed_counts: dict[str, int] = {}
    for seed in campaign["seeds"]:
        kind, operation, packet = _build_seed(contract, seed)
        if seed["name"] in seed_counts:
            raise AndroidFfiMutationViolation("duplicate seed name")
        seed_counts[seed["name"]] = len(packet) * 8
        for byte_index in range(len(packet)):
            for mask in campaign["bit_masks"]:
                mutated = bytearray(packet)
                mutated[byte_index] ^= mask
                try:
                    normalized = _decode_canonical(contract, kind, operation, bytes(mutated))
                    result = {"result": "accepted", "value": normalized}
                    outcomes["accepted"] += 1
                except AndroidFfiFrameViolation as error:
                    if error.code not in contract["decoder_errors"]:
                        raise AndroidFfiMutationViolation("unregistered rejection code") from error
                    result = {"result": "rejected", "code": error.code}
                    outcomes["rejected"] += 1
                    rejection_codes[error.code] += 1
                record = {
                    "seed": seed["name"],
                    "byte": byte_index,
                    "mask": mask,
                    "outcome": result,
                }
                digest.update(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())
                digest.update(b"\n")
    return {
        "seeds": len(campaign["seeds"]),
        "mutations": sum(seed_counts.values()),
        "outcomes": dict(sorted(outcomes.items())),
        "rejection_codes": dict(sorted(rejection_codes.items())),
        "mutations_by_seed": seed_counts,
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    """Print canonical campaign evidence for automation and review."""
    print(json.dumps(run_campaign(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
