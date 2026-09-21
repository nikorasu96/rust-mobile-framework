"""Regression tests for Android container ownership and detach semantics."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.android_container_model import (
    MAX_KOTLIN_LONG,
    AndroidContainerViolation,
    Binding,
    ContainerRegistry,
    apply_action,
)
from scripts.android_container_invariants import (
    AndroidContainerInvariantError,
    validate_state,
)
from scripts.check_android_container_exhaustive import explore
from scripts.check_android_container_fixtures import CONTRACT, run_scenarios, validate_contract


class AndroidContainerContractTests(unittest.TestCase):
    def test_reviewed_scenarios(self) -> None:
        self.assertEqual(run_scenarios(), {"scenarios": 11, "actions": 32})

    def test_rejection_is_atomic(self) -> None:
        model = ContainerRegistry()
        apply_action(
            model,
            {"type": "claim", "caller_thread": "main", "container_id": 1, "host_id": 10},
        )
        before = copy.deepcopy(model.snapshot())
        with self.assertRaisesRegex(AndroidContainerViolation, "CONTAINER_ALREADY_OWNED"):
            apply_action(
                model,
                {"type": "claim", "caller_thread": "main", "container_id": 1, "host_id": 11},
            )
        self.assertEqual(model.snapshot(), before)

    def test_mount_id_exhaustion_does_not_wrap(self) -> None:
        model = ContainerRegistry(next_mount_id=MAX_KOTLIN_LONG + 1)
        with self.assertRaisesRegex(AndroidContainerViolation, "MOUNT_ID_EXHAUSTED"):
            apply_action(
                model,
                {"type": "claim", "caller_thread": "main", "container_id": 1, "host_id": 10},
            )
        self.assertEqual(model.next_mount_id, MAX_KOTLIN_LONG + 1)

    def test_stale_result_cannot_remove_current_root(self) -> None:
        model = ContainerRegistry(
            next_mount_id=3,
            bindings={1: Binding(host_id=11, mount_id=2, state="ATTACHED", root_id=100)},
        )
        before = copy.deepcopy(model.snapshot())
        effect = apply_action(
            model,
            {
                "type": "attach_succeeded",
                "caller_thread": "main",
                "container_id": 1,
                "host_id": 10,
                "mount_id": 1,
                "root_id": 100,
            },
        )
        self.assertEqual(effect, {"type": "DROP_STALE_RESULT"})
        self.assertEqual(model.snapshot(), before)

    def test_boolean_is_not_a_valid_identity(self) -> None:
        with self.assertRaisesRegex(AndroidContainerViolation, "INVALID_ID"):
            apply_action(
                ContainerRegistry(),
                {"type": "claim", "caller_thread": "main", "container_id": True, "host_id": 10},
            )

    def test_contract_vocabulary_is_closed(self) -> None:
        changed = json.loads(CONTRACT.read_text(encoding="utf-8"))
        changed["effects"].append("REMOVE_ALL_VIEWS")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contract drift"):
                validate_contract(path)

    def test_bounded_exploration_is_reproducible(self) -> None:
        first = explore()
        second = explore()
        self.assertEqual(first, second)
        self.assertEqual(first["binding_states"], ["ATTACHED", "RESERVED"])
        self.assertEqual(len(first["effects"]), 7)
        self.assertEqual(len(first["errors"]), 5)

    def test_invariant_rejects_root_in_two_bindings(self) -> None:
        model = ContainerRegistry(
            next_mount_id=3,
            bindings={
                1: Binding(host_id=10, mount_id=1, state="ATTACHED", root_id=100),
                2: Binding(host_id=11, mount_id=2, state="ATTACHED", root_id=100),
            },
        )
        with self.assertRaisesRegex(AndroidContainerInvariantError, "multiple"):
            validate_state(model)


if __name__ == "__main__":
    unittest.main()
