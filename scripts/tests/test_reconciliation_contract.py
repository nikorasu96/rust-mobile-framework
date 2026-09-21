"""Regression tests for reconciliation contract metadata validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.reconciliation_batch_model import BatchApplicationError, apply_batch
from scripts.reconciliation_oracle import select_child_matches
from scripts.check_reconciliation_sequences import run_campaign
from scripts.reconciliation_validation import (
    ContractViolation,
    load_component_schemas,
    validate_transaction,
)


class ComponentSchemaTests(unittest.TestCase):
    """Exercise the real schema loader without replacing its dependencies."""

    @staticmethod
    def load(document: dict[str, object]) -> dict[str, dict[str, str]]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "components.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            return load_component_schemas(path)

    def test_accepts_supported_descriptor(self) -> None:
        schemas = self.load(
            {
                "schema_version": 1,
                "components": {
                    "Text": {"1": {"name": "content", "type": "string"}}
                },
            }
        )
        self.assertEqual(schemas, {"Text": {"1": "string"}})

    def test_rejects_unsupported_schema_version(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "unsupported schema document"):
            self.load({"schema_version": 2, "components": {"Text": {}}})

    def test_rejects_non_positive_property_id(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "positive decimals"):
            self.load(
                {
                    "schema_version": 1,
                    "components": {
                        "Text": {"0": {"name": "content", "type": "string"}}
                    },
                }
            )

    def test_rejects_open_ended_property_type(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "unsupported property type"):
            self.load(
                {
                    "schema_version": 1,
                    "components": {
                        "Text": {"1": {"name": "content", "type": "json"}}
                    },
                }
            )


class KeyedMatchingTests(unittest.TestCase):
    """Protect deterministic identity matching for wide keyed sibling lists."""

    def test_reverse_wide_list_uses_each_existing_identity_once(self) -> None:
        width = 2_048
        old_children = [
            {"node_id": index + 1, "kind": "Text", "key": f"item-{index}"}
            for index in range(width)
        ]
        candidate_children = [
            {"kind": "Text", "key": f"item-{index}"}
            for index in range(width - 1, -1, -1)
        ]

        expected = list(range(width - 1, -1, -1))
        first = select_child_matches(old_children, candidate_children)
        second = select_child_matches(old_children, candidate_children)

        self.assertEqual(first, expected)
        self.assertEqual(second, expected)
        self.assertEqual(len(set(first)), width)


class TransactionValidationTests(unittest.TestCase):
    """Exercise fail-closed transaction metadata without a renderer."""

    @staticmethod
    def fixture(limits: dict[str, object]) -> dict[str, object]:
        return {
            "contract_version": 1,
            "name": "transaction-validation",
            "base_revision": 0,
            "target_revision": 1,
            "allocator_next_id": 1,
            "limits": limits,
            "previous": None,
            "candidate": {"kind": "View", "key": None, "properties": {}, "children": []},
            "expected": {},
        }

    def test_rejects_every_invalid_limit_override_shape(self) -> None:
        invalid_overrides = (
            {"max_nodes": 0},
            {"max_nodes": -1},
            {"max_nodes": True},
            {"unknown_limit": 1},
        )
        for limits in invalid_overrides:
            with self.subTest(limits=limits):
                with self.assertRaises(ContractViolation) as captured:
                    validate_transaction(self.fixture(limits))
                self.assertEqual(captured.exception.code, "INVALID_LIMITS")


class MutationBatchModelTests(unittest.TestCase):
    """Exercise the independent host model's strict mutation preconditions."""

    def test_rejects_move_when_source_does_not_identify_child(self) -> None:
        previous = {
            "revision": 1,
            "root": {
                "node_id": 1,
                "kind": "View",
                "key": None,
                "properties": {},
                "children": [
                    {"node_id": 2, "kind": "Text", "key": "a", "properties": {}, "children": []},
                    {"node_id": 3, "kind": "Text", "key": "b", "properties": {}, "children": []},
                ],
            },
        }
        operations = [{"op": "MoveChild", "parent_id": 1, "child_id": 3, "from": 0, "to": 1}]

        with self.assertRaisesRegex(BatchApplicationError, "move source"):
            apply_batch(previous, operations)


class GeneratedSequenceTests(unittest.TestCase):
    """Protect reproducibility of the generated stateful invariant campaign."""

    def test_fixed_seeds_produce_identical_campaigns(self) -> None:
        first = run_campaign(seeds=(7, 19), steps_per_seed=10)
        second = run_campaign(seeds=(7, 19), steps_per_seed=10)

        self.assertEqual(first, second)
        self.assertEqual(first["transitions"], 20)

if __name__ == "__main__":
    unittest.main()
