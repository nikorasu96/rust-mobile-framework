"""Regression tests for surface lifecycle and generational handles."""

from __future__ import annotations

import unittest

from scripts.check_surface_lifecycle_fixtures import (
    SurfaceLifecycleViolation,
    transition,
    validate_handle,
    validate_state,
)
from scripts.check_surface_lifecycle_sequences import run_campaign
from scripts.check_surface_lifecycle_exhaustive import explore


class SurfaceLifecycleContractTests(unittest.TestCase):
    def test_rejects_zero_and_boolean_handle_fields(self) -> None:
        for handle in (
            {"surface_id": 0, "generation": 1},
            {"surface_id": 1, "generation": False},
        ):
            with self.subTest(handle=handle):
                with self.assertRaisesRegex(SurfaceLifecycleViolation, "positive u64"):
                    validate_handle(handle)

    def test_rejects_allocator_behind_active_generation(self) -> None:
        state = {
            "allocator": {"status": "available", "next": 3},
            "active": [{"surface_id": 1, "generation": 3}],
        }
        with self.assertRaisesRegex(SurfaceLifecycleViolation, "allocator"):
            validate_state(state)

    def test_stale_dispose_preserves_replacement(self) -> None:
        state = {
            "allocator": {"status": "available", "next": 3},
            "active": [{"surface_id": 7, "generation": 2}],
        }
        next_state, output = transition(
            state,
            {"op": "dispose", "handle": {"surface_id": 7, "generation": 1}},
        )
        self.assertEqual(next_state, state)
        self.assertEqual(output, {"result": "rejected", "code": "STALE_SURFACE_HANDLE"})

    def test_duplicate_create_does_not_consume_generation(self) -> None:
        state = {
            "allocator": {"status": "available", "next": 2},
            "active": [{"surface_id": 7, "generation": 1}],
        }
        next_state, output = transition(state, {"op": "create", "surface_id": 7})
        self.assertEqual(next_state, state)
        self.assertEqual(output, {"result": "rejected", "code": "SURFACE_ALREADY_ACTIVE"})

    def test_generated_lifecycle_campaign_is_reproducible(self) -> None:
        first = run_campaign(seeds=(13, 29), steps_per_seed=35)
        second = run_campaign(seeds=(13, 29), steps_per_seed=35)

        self.assertEqual(first, second)
        self.assertEqual(first["actions"], 70)

    def test_bounded_lifecycle_exploration_is_reproducible(self) -> None:
        first = explore(max_depth=4)
        second = explore(max_depth=4)

        self.assertEqual(first, second)
        self.assertEqual(first["actions_per_state"], 18)
        self.assertEqual(first["active_peak"], 2)


if __name__ == "__main__":
    unittest.main()
