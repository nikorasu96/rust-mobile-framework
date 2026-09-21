"""Regression tests for composed Android host orchestration."""

from __future__ import annotations

import copy
import unittest

from scripts.android_container_model import Binding, ContainerRegistry
from scripts.android_facade_model import MAX_KOTLIN_LONG
from scripts.android_host_composition_model import (
    AndroidHostCompositionViolation,
    AndroidHostState,
    apply_action,
)
from scripts.check_android_host_composition import run_scenarios, validate_invariants


BEGIN = {
    "type": "begin",
    "caller_thread": "main",
    "container_id": 1,
    "host_id": 10,
    "surface_id": 100,
    "root_id": 1000,
}


class AndroidHostCompositionTests(unittest.TestCase):
    def test_reviewed_scenarios(self) -> None:
        metrics = run_scenarios()
        self.assertEqual(metrics["scenarios"], 7)
        self.assertEqual(metrics["actions"], 21)

    def test_foreign_container_is_preserved_on_start_failure(self) -> None:
        containers = ContainerRegistry(
            next_mount_id=2,
            bindings={1: Binding(host_id=99, mount_id=1, state="ATTACHED", root_id=999)},
        )
        model = AndroidHostState(containers=containers)
        before = copy.deepcopy(containers.snapshot())
        result = apply_action(model, BEGIN)
        self.assertEqual(result, {"type": "START_FAILED", "reason": "CONTAINER_ALREADY_OWNED"})
        self.assertEqual(model.containers.snapshot(), before)
        self.assertEqual(model.facade.state, "FAILED")
        validate_invariants(model)

    def test_surface_collision_cleans_only_new_host_resources(self) -> None:
        model = AndroidHostState(
            surfaces={
                "allocator": {"status": "available", "next": 2},
                "active": [{"surface_id": 100, "generation": 1}],
            }
        )
        apply_action(model, BEGIN)
        result = apply_action(
            model, {"type": "native_create_succeeded", "caller_thread": "main"}
        )
        self.assertEqual(result, {"type": "START_FAILED", "reason": "SURFACE_ALREADY_ACTIVE"})
        self.assertEqual(
            model.surfaces["active"], [{"surface_id": 100, "generation": 1}]
        )
        self.assertEqual(model.containers.snapshot()["bindings"], {})
        validate_invariants(model)

    def test_generation_outside_kotlin_range_is_disposed_and_fails_closed(self) -> None:
        model = AndroidHostState(
            surfaces={
                "allocator": {"status": "available", "next": MAX_KOTLIN_LONG + 1},
                "active": [],
            }
        )
        apply_action(model, BEGIN)
        result = apply_action(
            model, {"type": "native_create_succeeded", "caller_thread": "main"}
        )
        self.assertEqual(result, {"type": "START_FAILED", "reason": "HANDLE_OUT_OF_RANGE"})
        self.assertEqual(model.surfaces["active"], [])
        self.assertEqual(model.containers.snapshot()["bindings"], {})
        validate_invariants(model)

    def test_root_collision_preserves_existing_binding(self) -> None:
        model = AndroidHostState(
            containers=ContainerRegistry(
                next_mount_id=2,
                bindings={9: Binding(host_id=90, mount_id=1, state="ATTACHED", root_id=1000)},
            )
        )
        result = apply_action(model, BEGIN)
        self.assertEqual(result, {"type": "START_FAILED", "reason": "ROOT_NOT_DETACHED"})
        self.assertEqual(
            model.containers.snapshot()["bindings"],
            {"9": {"host_id": 90, "mount_id": 1, "state": "ATTACHED", "root_id": 1000}},
        )
        validate_invariants(model)

    def test_invalid_identity_rejects_before_any_claim(self) -> None:
        model = AndroidHostState()
        action = {**BEGIN, "surface_id": False}
        before = copy.deepcopy(model.snapshot())
        with self.assertRaisesRegex(AndroidHostCompositionViolation, "INVALID_ID"):
            apply_action(model, action)
        self.assertEqual(model.snapshot(), before)

    def test_callback_must_pass_surface_gate_before_facade_sequence_gate(self) -> None:
        model = AndroidHostState()
        apply_action(model, BEGIN)
        apply_action(model, {"type": "native_create_succeeded", "caller_thread": "main"})
        before_sequence = model.facade.last_sequence
        result = apply_action(
            model,
            {
                "type": "callback",
                "caller_thread": "main",
                "surface_id": 100,
                "generation": 2,
                "sequence": 9,
            },
        )
        self.assertEqual(result["type"], "CALLBACK_DROPPED")
        self.assertEqual(model.facade.last_sequence, before_sequence)

    def test_invalid_transition_does_not_create_surface(self) -> None:
        model = AndroidHostState(surface_id=100)
        before = copy.deepcopy(model.snapshot())
        with self.assertRaisesRegex(AndroidHostCompositionViolation, "INVALID_TRANSITION"):
            apply_action(model, {"type": "native_create_succeeded", "caller_thread": "main"})
        self.assertEqual(model.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
