"""Validation rules for reconciliation v1 contracts."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

DEFAULT_LIMITS = {
    "max_depth": 256,
    "max_nodes": 100_000,
    "max_children_per_node": 10_000,
    "max_properties_per_node": 256,
    "max_string_bytes": 1_048_576,
    "max_operations": 1_000_000,
}
PROPERTY_TYPES = frozenset({"bool", "i64", "f64", "string"})
NODE_FIELDS = frozenset({"kind", "key", "properties", "children"})
COMMITTED_NODE_FIELDS = NODE_FIELDS | {"node_id"}
COMMITTED_TREE_FIELDS = frozenset({"revision", "root"})
TRANSACTION_FIELDS = frozenset(
    {
        "contract_version",
        "base_revision",
        "target_revision",
        "allocator_next_id",
        "previous",
        "candidate",
    }
)
FIXTURE_FIELDS = TRANSACTION_FIELDS | {"name", "expected"}


class ContractViolation(Exception):
    """Typed fixture or candidate contract failure."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code



def load_component_schemas(path: Path) -> dict[str, dict[str, str]]:
    """Load and validate the versioned component/property registry."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or set(document) != {"schema_version", "components"}:
        raise ContractViolation("INVALID_COMPONENT_SCHEMA", "unsupported schema document")
    components = document["components"]
    if not isinstance(components, dict) or not components:
        raise ContractViolation("INVALID_COMPONENT_SCHEMA", "components must be a non-empty object")

    schemas: dict[str, dict[str, str]] = {}
    for component_kind, properties in components.items():
        if not isinstance(component_kind, str) or not component_kind or not isinstance(properties, dict):
            raise ContractViolation("INVALID_COMPONENT_SCHEMA", "invalid component entry")
        schemas[component_kind] = {}
        for property_id, descriptor in properties.items():
            if not property_id.isdecimal() or int(property_id) <= 0:
                raise ContractViolation("INVALID_COMPONENT_SCHEMA", "property IDs must be positive decimals")
            if not isinstance(descriptor, dict) or set(descriptor) != {"name", "type"}:
                raise ContractViolation("INVALID_COMPONENT_SCHEMA", "invalid property descriptor")
            if not isinstance(descriptor["name"], str) or not descriptor["name"]:
                raise ContractViolation("INVALID_COMPONENT_SCHEMA", "property names must be non-empty")
            if descriptor["type"] not in PROPERTY_TYPES:
                raise ContractViolation("INVALID_COMPONENT_SCHEMA", "unsupported property type")
            schemas[component_kind][property_id] = descriptor["type"]
    return schemas


def validate_property(
    component_kind: str,
    property_id: str,
    value: dict[str, Any],
    limits: dict[str, int],
    schemas: dict[str, dict[str, str]],
) -> None:
    """Validate the closed v1 property value family."""
    if not property_id.isdecimal() or int(property_id) <= 0:
        raise ContractViolation("INVALID_PROPERTY_ID", f"invalid property id: {property_id}")
    if not isinstance(value, dict) or set(value) != {"type", "value"}:
        raise ContractViolation("INVALID_PROPERTY_VALUE", f"malformed property {property_id}")
    kind = value["type"]
    raw_value = value["value"]
    valid = False
    if kind == "bool":
        valid = isinstance(raw_value, bool)
    elif kind == "i64":
        valid = (
            isinstance(raw_value, int)
            and not isinstance(raw_value, bool)
            and -(2**63) <= raw_value < 2**63
        )
    elif kind == "f64":
        valid = (
            isinstance(raw_value, (int, float))
            and not isinstance(raw_value, bool)
            and math.isfinite(raw_value)
        )
    elif kind == "string":
        valid = isinstance(raw_value, str)
        if valid and len(raw_value.encode("utf-8")) > limits["max_string_bytes"]:
            raise ContractViolation("STRING_BYTES_LIMIT", f"property {property_id} is too large")
    if not valid:
        raise ContractViolation("INVALID_PROPERTY_VALUE", f"invalid {kind} property {property_id}")
    component_schema = schemas.get(component_kind)
    if component_schema is None:
        raise ContractViolation("UNKNOWN_COMPONENT_KIND", f"unknown component kind: {component_kind}")
    expected_kind = component_schema.get(property_id)
    if expected_kind is None:
        raise ContractViolation(
            "UNSUPPORTED_PROPERTY", f"property {property_id} is unsupported by {component_kind}"
        )
    if kind != expected_kind:
        raise ContractViolation(
            "INVALID_PROPERTY_TYPE",
            f"property {property_id} on {component_kind} requires {expected_kind}, received {kind}",
        )


def validate_fixture_envelope(fixture: Any) -> None:
    """Validate fixture-only metadata around a reconciliation transaction."""
    if not isinstance(fixture, dict) or not FIXTURE_FIELDS.issubset(fixture):
        raise ContractViolation("INVALID_TRANSACTION_STRUCTURE", "missing transaction fields")
    if set(fixture) - FIXTURE_FIELDS - {"limits"}:
        raise ContractViolation("INVALID_TRANSACTION_STRUCTURE", "unexpected transaction fields")
    if not isinstance(fixture["name"], str) or not fixture["name"]:
        raise ContractViolation("INVALID_TRANSACTION_STRUCTURE", "fixture name must be non-empty")
    if not isinstance(fixture["expected"], dict):
        raise ContractViolation("INVALID_TRANSACTION_STRUCTURE", "expected result must be an object")


def validate_transaction(fixture: Any) -> dict[str, int]:
    """Validate the reconciliation request and return effective limits."""
    validate_fixture_envelope(fixture)
    if fixture["contract_version"] != 1:
        raise ContractViolation("UNSUPPORTED_CONTRACT", "only contract version 1 is supported")

    base_revision = fixture["base_revision"]
    target_revision = fixture["target_revision"]
    revisions_are_integers = (
        isinstance(base_revision, int)
        and not isinstance(base_revision, bool)
        and isinstance(target_revision, int)
        and not isinstance(target_revision, bool)
    )
    if not revisions_are_integers or base_revision < 0 or target_revision != base_revision + 1:
        raise ContractViolation("INVALID_REVISION", "target revision must immediately follow base")

    allocator_next_id = fixture["allocator_next_id"]
    if (
        not isinstance(allocator_next_id, int)
        or isinstance(allocator_next_id, bool)
        or allocator_next_id <= 0
    ):
        raise ContractViolation("INVALID_ALLOCATOR_STATE", "next node ID must be a positive integer")
    if fixture["previous"] is not None and not isinstance(fixture["previous"], dict):
        raise ContractViolation("INVALID_TRANSACTION_STRUCTURE", "previous must be an object or null")

    overrides = fixture.get("limits", {})
    if not isinstance(overrides, dict) or set(overrides) - set(DEFAULT_LIMITS):
        raise ContractViolation("INVALID_LIMITS", "limits contain unknown fields")
    for name, value in overrides.items():
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ContractViolation("INVALID_LIMITS", f"limit {name} must be a positive integer")
    return DEFAULT_LIMITS | overrides


def validate_candidate(
    node: Any,
    limits: dict[str, int],
    schemas: dict[str, dict[str, str]],
    depth: int = 1,
) -> int:
    """Validate values, limits and key uniqueness before producing mutations."""
    if not isinstance(node, dict) or set(node) != NODE_FIELDS:
        raise ContractViolation(
            "INVALID_NODE_STRUCTURE", "candidate nodes require only kind, key, properties and children"
        )
    if not isinstance(node["kind"], str) or not node["kind"]:
        raise ContractViolation("INVALID_NODE_STRUCTURE", "component kind must be a non-empty string")
    if node["key"] is not None and not isinstance(node["key"], str):
        raise ContractViolation("INVALID_NODE_STRUCTURE", "node key must be a string or null")
    if not isinstance(node["properties"], dict) or not isinstance(node["children"], list):
        raise ContractViolation("INVALID_NODE_STRUCTURE", "properties and children have invalid types")
    if node["kind"] not in schemas:
        raise ContractViolation("UNKNOWN_COMPONENT_KIND", f"unknown component kind: {node['kind']}")
    if depth > limits["max_depth"]:
        raise ContractViolation("TREE_DEPTH_LIMIT", f"tree depth exceeds {limits['max_depth']}")
    if len(node["children"]) > limits["max_children_per_node"]:
        raise ContractViolation("CHILD_COUNT_LIMIT", "too many direct children on a node")
    if len(node["properties"]) > limits["max_properties_per_node"]:
        raise ContractViolation("PROPERTY_COUNT_LIMIT", "too many properties on a node")
    for property_id, value in node["properties"].items():
        validate_property(node["kind"], property_id, value, limits, schemas)
    keys: set[str] = set()
    node_count = 1
    for child in node["children"]:
        key = child["key"]
        if key is not None and key in keys:
            raise ContractViolation("DUPLICATE_SIBLING_KEY", f"duplicate sibling key: {key}")
        if key is not None:
            keys.add(key)
        node_count += validate_candidate(child, limits, schemas, depth + 1)
        if node_count > limits["max_nodes"]:
            raise ContractViolation("NODE_COUNT_LIMIT", f"tree contains over {limits['max_nodes']} nodes")
    return node_count


def validate_committed_node(
    node: Any,
    limits: dict[str, int],
    schemas: dict[str, dict[str, str]],
    seen_ids: set[int],
    depth: int = 1,
) -> tuple[int, int]:
    """Validate one committed subtree and return its node count and maximum ID."""
    if not isinstance(node, dict) or set(node) != COMMITTED_NODE_FIELDS:
        raise ContractViolation("INVALID_COMMITTED_TREE", "committed node fields are invalid")
    node_id = node["node_id"]
    if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id <= 0:
        raise ContractViolation("INVALID_COMMITTED_TREE", "node IDs must be positive integers")
    if node_id in seen_ids:
        raise ContractViolation("INVALID_COMMITTED_TREE", f"duplicate node ID: {node_id}")
    seen_ids.add(node_id)
    if not isinstance(node["kind"], str) or not node["kind"] or node["kind"] not in schemas:
        raise ContractViolation("INVALID_COMMITTED_TREE", "committed component kind is invalid")
    if node["key"] is not None and not isinstance(node["key"], str):
        raise ContractViolation("INVALID_COMMITTED_TREE", "committed key is invalid")
    if not isinstance(node["properties"], dict) or not isinstance(node["children"], list):
        raise ContractViolation("INVALID_COMMITTED_TREE", "committed collections are invalid")
    if depth > limits["max_depth"]:
        raise ContractViolation("TREE_DEPTH_LIMIT", f"tree depth exceeds {limits['max_depth']}")
    if len(node["children"]) > limits["max_children_per_node"]:
        raise ContractViolation("CHILD_COUNT_LIMIT", "too many direct children on a node")
    if len(node["properties"]) > limits["max_properties_per_node"]:
        raise ContractViolation("PROPERTY_COUNT_LIMIT", "too many properties on a node")
    for property_id, value in node["properties"].items():
        validate_property(node["kind"], property_id, value, limits, schemas)

    keys: set[str] = set()
    node_count = 1
    max_node_id = node_id
    for child in node["children"]:
        if not isinstance(child, dict):
            raise ContractViolation("INVALID_COMMITTED_TREE", "committed child is invalid")
        key = child.get("key")
        if key is not None and key in keys:
            raise ContractViolation("INVALID_COMMITTED_TREE", f"duplicate committed key: {key}")
        if key is not None:
            keys.add(key)
        child_count, child_max_id = validate_committed_node(
            child, limits, schemas, seen_ids, depth + 1
        )
        node_count += child_count
        max_node_id = max(max_node_id, child_max_id)
        if node_count > limits["max_nodes"]:
            raise ContractViolation("NODE_COUNT_LIMIT", f"tree contains over {limits['max_nodes']} nodes")
    return node_count, max_node_id


def validate_committed_tree(
    previous: dict[str, Any], limits: dict[str, int], schemas: dict[str, dict[str, str]]
) -> int:
    """Validate committed-tree structure and return its greatest runtime identity."""
    if set(previous) != COMMITTED_TREE_FIELDS:
        raise ContractViolation("INVALID_COMMITTED_TREE", "committed tree fields are invalid")
    revision = previous["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ContractViolation("INVALID_COMMITTED_TREE", "committed revision is invalid")
    _, max_node_id = validate_committed_node(previous["root"], limits, schemas, set())
    return max_node_id


