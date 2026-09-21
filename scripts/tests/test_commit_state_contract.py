"""Regression tests for the commit-application state contract."""

from __future__ import annotations

import unittest

from scripts.check_commit_state_fixtures import (
    CommitContractViolation,
    execute,
    transition,
    validate_fixture,
    validate_state,
)
from scripts.check_commit_state_sequences import run_campaign
from scripts.check_commit_state_exhaustive import explore


class CommitStateContractTests(unittest.TestCase):
    def test_rejects_nonconsecutive_recovery_revisions(self) -> None:
        state = {
            "state": "failed",
            "revision": 4,
            "attempted_revision": 6,
            "failure_code": "HOST_FAILED",
        }

        with self.assertRaisesRegex(CommitContractViolation, "consecutive"):
            validate_state(state)

    def test_rejects_unexpected_action_field(self) -> None:
        fixture = {
            "contract_version": 1,
            "name": "invalid-action",
            "initial": {"state": "ready", "revision": 0},
            "actions": [
                {"op": "host_applied", "unexpected": True},
            ],
            "expected": {},
        }
        with self.assertRaisesRegex(CommitContractViolation, "invalid fields"):
            validate_fixture(fixture)

    def test_failed_surface_rejects_new_commit(self) -> None:
        state = {
            "state": "failed",
            "revision": 4,
            "attempted_revision": 5,
            "failure_code": "HOST_FAILED",
        }
        action = {"op": "begin_apply", "base_revision": 4, "target_revision": 5}

        next_state, output = transition(state, action)

        self.assertEqual(next_state, state)
        self.assertEqual(output, {"result": "rejected", "code": "RECOVERY_REQUIRED"})

    def test_safe_rejection_never_promotes_revision(self) -> None:
        fixture = {
            "contract_version": 1,
            "name": "safe-rejection",
            "initial": {"state": "ready", "revision": 1},
            "actions": [
                {"op": "begin_apply", "base_revision": 1, "target_revision": 2},
                {"op": "host_rejected", "code": "VALIDATION_FAILED"},
            ],
            "expected": {},
        }

        result = execute(fixture)

        self.assertEqual(result["final"], {"state": "ready", "revision": 1})

    def test_generated_campaign_is_reproducible(self) -> None:
        first = run_campaign(seeds=(11, 23), steps_per_seed=25)
        second = run_campaign(seeds=(11, 23), steps_per_seed=25)

        self.assertEqual(first, second)
        self.assertEqual(first["actions"], 50)

    def test_bounded_exploration_is_reproducible_and_complete(self) -> None:
        first = explore(max_depth=4)
        second = explore(max_depth=4)

        self.assertEqual(first, second)
        self.assertEqual(set(first["state_types"]), {"ready", "applying", "failed", "remounting"})
        self.assertEqual(len(first["action_types"]), 7)


if __name__ == "__main__":
    unittest.main()
