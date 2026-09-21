"""Regression tests for the Android JNI admission contract."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.android_ffi_bodies import (
    decode_commit_result_body,
    decode_event_body,
    encode_commit_result_body,
    encode_event_body,
)
from scripts.check_android_ffi_fixtures import (
    AndroidFfiContractViolation,
    admit,
    load_contract,
)
from scripts.android_ffi_frames import (
    AndroidFfiFrameViolation,
    decode_operation_payload,
    decode_response_frame,
    encode_operation_payload,
    encode_response_frame,
)
from scripts.check_android_ffi_frame_corpus import CORPUS_DIRECTORY, execute_corpus
from scripts.check_android_ffi_body_corpus import execute_corpus as execute_body_corpus
from scripts.check_android_ffi_mutations import run_campaign


class AndroidFfiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.valid_create = {
            "abi_version": 1,
            "operation": 1,
            "request_id": 1,
            "surface_id": 1,
            "generation": 0,
            "payload_hex": "",
            "caller_thread": "main",
        }

    def test_contract_rejects_descriptor_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["jni_method"]["descriptor"] = "(J)V"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(AndroidFfiContractViolation, "JNI method"):
                load_contract(path)

    def test_boolean_is_not_a_transport_identifier(self) -> None:
        request = {**self.valid_create, "request_id": True}
        self.assertEqual(admit(self.contract, request)["code"], "INVALID_ARGUMENT")

    def test_boolean_is_not_an_abi_version(self) -> None:
        request = {**self.valid_create, "abi_version": True}
        self.assertEqual(admit(self.contract, request)["code"], "INVALID_ARGUMENT")

    def test_unknown_operation_fails_closed(self) -> None:
        request = {**self.valid_create, "operation": 99}
        self.assertEqual(admit(self.contract, request)["code"], "UNKNOWN_OPERATION")

    def test_payload_limit_is_enforced_at_exact_boundary(self) -> None:
        maximum = self.contract["limits"]["max_payload_bytes"]
        exact = encode_operation_payload(
            self.contract,
            operation=3,
            body=b"\x00" * (maximum - 16),
        )
        self.assertEqual(len(exact), maximum)
        base = {**self.valid_create, "operation": 3, "generation": 1, "payload_hex": exact.hex()}
        self.assertEqual(admit(self.contract, base)["code"], "INVALID_ARGUMENT")
        oversized = {**base, "payload_hex": exact.hex() + "00"}
        self.assertEqual(admit(self.contract, oversized)["code"], "PAYLOAD_TOO_LARGE")

    def test_closed_input_rejects_unexpected_field(self) -> None:
        request = {**self.valid_create, "native_pointer": 7}
        self.assertEqual(admit(self.contract, request)["code"], "INVALID_ARGUMENT")

    def test_manifest_loader_is_strict(self) -> None:
        self.assertEqual(self.contract["jni_method"]["descriptor"], "(IIJJJ[B)[B")
        self.assertEqual(self.contract["status_codes"]["INTERNAL_PANIC"], 900)

    def test_response_frame_has_exact_stable_bytes(self) -> None:
        encoded = encode_response_frame(self.contract, status=0, request_id=1)
        self.assertEqual(len(encoded), 32)
        self.assertEqual(
            encoded.hex(),
            "524d463101002000000000000000000001000000000000000000000000000000",
        )

    def test_response_frame_rejects_unregistered_status(self) -> None:
        with self.assertRaisesRegex(AndroidFfiFrameViolation, "UNKNOWN_STATUS"):
            encode_response_frame(self.contract, status=777, request_id=1)

    def test_response_frame_round_trip_preserves_owned_payload(self) -> None:
        encoded = encode_response_frame(self.contract, status=0, request_id=9, payload=b"\x00\xff")
        self.assertEqual(
            decode_response_frame(self.contract, encoded),
            {"abi_version": 1, "status": 0, "request_id": 9, "payload_hex": "00ff"},
        )

    def test_operation_payload_round_trip_checks_discriminator(self) -> None:
        encoded = encode_operation_payload(self.contract, operation=3, body=b"event")
        self.assertEqual(
            decode_operation_payload(self.contract, expected_operation=3, data=encoded),
            {"schema_version": 1, "operation": 3, "body_hex": "6576656e74"},
        )
        with self.assertRaisesRegex(AndroidFfiFrameViolation, "PAYLOAD_OPERATION_MISMATCH"):
            decode_operation_payload(self.contract, expected_operation=4, data=encoded)

    def test_admission_rejects_corrupt_operation_payload(self) -> None:
        request = {
            **self.valid_create,
            "operation": 3,
            "generation": 1,
            "payload_hex": "524d5031010003000200000000000000aa",
        }
        self.assertEqual(admit(self.contract, request)["code"], "INVALID_ARGUMENT")

    def test_event_body_round_trip_is_typed(self) -> None:
        encoded = encode_event_body(self.contract, node_id=42, event_code=1, sequence=9)
        self.assertEqual(len(encoded), 24)
        self.assertEqual(
            decode_event_body(self.contract, encoded),
            {"node_id": 42, "event": "CLICK", "sequence": 9},
        )

    def test_commit_result_round_trip_enforces_classification(self) -> None:
        encoded = encode_commit_result_body(
            self.contract,
            base_revision=4,
            target_revision=5,
            outcome=3,
            reason=2,
        )
        self.assertEqual(
            decode_commit_result_body(self.contract, encoded),
            {
                "base_revision": 4,
                "target_revision": 5,
                "outcome": "FAILED_AFTER_MUTATION",
                "reason": "HOST_UNAVAILABLE",
            },
        )

    def test_commit_result_rejects_invalid_outcome_reason_pair(self) -> None:
        with self.assertRaisesRegex(AndroidFfiFrameViolation, "INVALID_OUTCOME_REASON"):
            encode_commit_result_body(
                self.contract,
                base_revision=4,
                target_revision=5,
                outcome=1,
                reason=1,
            )

    def test_reviewed_typed_body_corpus_is_complete(self) -> None:
        self.assertEqual(execute_body_corpus(contract=self.contract), (15, []))

    def test_single_bit_mutation_campaign_is_reproducible(self) -> None:
        evidence = run_campaign()
        self.assertEqual(evidence["seeds"], 7)
        self.assertEqual(evidence["mutations"], 2_128)
        self.assertEqual(evidence["outcomes"], {"accepted": 271, "rejected": 1_857})
        self.assertEqual(
            evidence["sha256"],
            "9e31a82ad3bb38bf8aa8881b9428a6292eacd7ea5b8ad5aba93ecbac8b7da37b",
        )

    def test_mutation_campaign_covers_every_registered_decoder_error(self) -> None:
        covered = set(run_campaign()["rejection_codes"])
        expected = set(self.contract["decoder_errors"]) - {
            "TRUNCATED_HEADER",
            "TRUNCATED_PAYLOAD_HEADER",
            "EMPTY_PAYLOAD_BODY",
            "INVALID_BODY_LENGTH",
        }
        self.assertEqual(covered, expected)

    def test_reviewed_frame_corpora_are_complete(self) -> None:
        results = {
            path.name: execute_corpus(path, self.contract)
            for path in (
                CORPUS_DIRECTORY / "operation-payloads.json",
                CORPUS_DIRECTORY / "response-frames.json",
            )
        }
        self.assertEqual(results["response-frames.json"], (10, []))
        self.assertEqual(results["operation-payloads.json"], (9, []))


if __name__ == "__main__":
    unittest.main()
