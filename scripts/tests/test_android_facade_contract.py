"""Regression tests for the future public Kotlin surface facade."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.android_facade_invariants import AndroidFacadeInvariantError, validate_state
from scripts.android_facade_model import AndroidFacadeViolation, FacadeState, apply_action
from scripts.check_android_facade_exhaustive import explore
from scripts.check_android_facade_fixtures import (
    AndroidFacadeContractViolation,
    CONTRACT_DIRECTORY,
    execute_fixture,
    load_contract,
)


class AndroidFacadeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_all_reviewed_scenarios_pass(self) -> None:
        paths = sorted(CONTRACT_DIRECTORY.glob("[0-9][0-9]-*.json"))
        self.assertEqual(len(paths), 12)
        for path in paths:
            fixture = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(execute_fixture(self.contract, fixture), fixture["expected"])

    def test_contract_rejects_action_registry_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["actions"].append("unsafe_reset")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(AndroidFacadeContractViolation, "unexpected actions"):
                load_contract(path)

    def test_worker_close_posts_once_and_disposes_once(self) -> None:
        model = FacadeState(state="ACTIVE", handle=(11, 3))
        first = apply_action(model, {"type": "request_close", "caller_thread": "worker"})
        second = apply_action(model, {"type": "request_close", "caller_thread": "worker"})
        drain = apply_action(model, {"type": "main_drain_close", "caller_thread": "main"})
        repeated = apply_action(model, {"type": "request_close", "caller_thread": "main"})
        self.assertEqual(first, {"type": "POST_CLOSE_TO_MAIN"})
        self.assertEqual(second, {"type": "NONE"})
        self.assertEqual(
            drain,
            {"type": "CALL_NATIVE_DISPOSE", "surface_id": 11, "generation": 3},
        )
        self.assertEqual(repeated, {"type": "NONE"})

    def test_off_main_native_result_does_not_mutate_state(self) -> None:
        model = FacadeState(state="CREATING")
        with self.assertRaisesRegex(AndroidFacadeViolation, "WRONG_THREAD"):
            apply_action(
                model,
                {
                    "type": "native_create_succeeded",
                    "caller_thread": "worker",
                    "surface_id": 1,
                    "generation": 1,
                },
            )
        self.assertEqual(model.snapshot(), FacadeState(state="CREATING").snapshot())

    def test_transport_identifier_cannot_exceed_kotlin_long(self) -> None:
        model = FacadeState(state="CREATING")
        with self.assertRaisesRegex(AndroidFacadeViolation, "INVALID_HANDLE"):
            apply_action(
                model,
                {
                    "type": "native_create_succeeded",
                    "caller_thread": "main",
                    "surface_id": 1 << 63,
                    "generation": 1,
                },
            )

    def test_bounded_exploration_is_reproducible(self) -> None:
        evidence = explore()
        self.assertEqual(evidence["actions_per_node"], 32)
        self.assertEqual(evidence["transitions_checked"], 4_832)
        self.assertEqual(evidence["unique_nodes"], 39)
        self.assertEqual(
            evidence["reachable_by_depth"], [1, 5, 12, 22, 33, 39, 39, 39]
        )
        self.assertEqual(
            evidence["sha256"],
            "1b1a683bac60140fabeb301fb714cb0f18b456e969f592f9932f61ff59540495",
        )

    def test_state_invariant_rejects_handle_in_closed_facade(self) -> None:
        with self.assertRaisesRegex(AndroidFacadeInvariantError, "handle"):
            validate_state(
                FacadeState(state="CLOSED", handle=(1, 1)),
                set(self.contract["states"]),
            )

    def test_exploration_depth_rejects_boolean(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            explore(True)


if __name__ == "__main__":
    unittest.main()
