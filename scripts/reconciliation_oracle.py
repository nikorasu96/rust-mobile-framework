"""Deterministic reconciliation oracle for contract fixtures."""

from __future__ import annotations

import copy
from typing import Any

if __package__:
    from .reconciliation_validation import (
        ContractViolation,
        validate_candidate,
        validate_committed_tree,
        validate_transaction,
    )
else:
    from reconciliation_validation import (
        ContractViolation,
        validate_candidate,
        validate_committed_tree,
        validate_transaction,
    )

class Allocator:
    """Monotonic runtime identity allocator used by the reference oracle."""

    def __init__(self, next_id: int):
        self.next_id = next_id

    def allocate(self) -> int:
        node_id = self.next_id
        self.next_id += 1
        return node_id

def property_delta(previous: dict[str, Any], candidate: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return deterministic set and remove property deltas."""
    changed = {
        key: value
        for key, value in sorted(candidate.items())
        if key not in previous or previous[key] != value
    }
    removed = sorted(key for key in previous if key not in candidate)
    return changed, removed


def create_subtree(
    candidate: dict[str, Any], allocator: Allocator, operations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a committed subtree and append topologically ordered operations."""
    node_id = allocator.allocate()
    operations.append({"op": "Create", "node_id": node_id, "kind": candidate["kind"]})
    if candidate["properties"]:
        operations.append(
            {
                "op": "UpdateProperties",
                "node_id": node_id,
                "set": copy.deepcopy(candidate["properties"]),
                "remove": [],
            }
        )

    children = []
    for index, child_candidate in enumerate(candidate["children"]):
        child = create_subtree(child_candidate, allocator, operations)
        children.append(child)
        operations.append(
            {"op": "InsertChild", "parent_id": node_id, "child_id": child["node_id"], "index": index}
        )

    return {
        "node_id": node_id,
        "kind": candidate["kind"],
        "key": candidate["key"],
        "properties": copy.deepcopy(candidate["properties"]),
        "children": children,
    }


def delete_subtree(node: dict[str, Any], operations: list[dict[str, Any]]) -> None:
    """Delete descendants before their ancestor."""
    for index in range(len(node["children"]) - 1, -1, -1):
        child = node["children"][index]
        operations.append(
            {"op": "RemoveChild", "parent_id": node["node_id"], "child_id": child["node_id"], "index": index}
        )
        delete_subtree(child, operations)
    operations.append({"op": "Delete", "node_id": node["node_id"]})


def matches(previous: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Return whether a candidate preserves a previous node identity."""
    return previous["kind"] == candidate["kind"] and previous["key"] == candidate["key"]


def select_child_matches(
    old_children: list[dict[str, Any]], candidate_children: list[dict[str, Any]]
) -> list[int | None]:
    """Select reusable children with one indexed lookup per keyed candidate."""
    keyed_old = {
        child["key"]: old_index
        for old_index, child in enumerate(old_children)
        if child["key"] is not None
    }
    used: set[int] = set()
    selected: list[int | None] = []
    for new_index, child_candidate in enumerate(candidate_children):
        if child_candidate["key"] is not None:
            selected_index = keyed_old.get(child_candidate["key"])
            if (
                selected_index is not None
                and selected_index not in used
                and not matches(old_children[selected_index], child_candidate)
            ):
                selected_index = None
        elif new_index < len(old_children):
            old_child = old_children[new_index]
            selected_index = new_index
            if selected_index in used or old_child["key"] is not None or not matches(
                old_child, child_candidate
            ):
                selected_index = None
        else:
            selected_index = None
        if selected_index is not None:
            used.add(selected_index)
        selected.append(selected_index)
    return selected


def reconcile_node(
    previous: dict[str, Any],
    candidate: dict[str, Any],
    allocator: Allocator,
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reconcile a matched node and return its next committed representation."""
    changed, removed = property_delta(previous["properties"], candidate["properties"])
    if changed or removed:
        operations.append(
            {"op": "UpdateProperties", "node_id": previous["node_id"], "set": changed, "remove": removed}
        )

    old_children = previous["children"]
    selected = select_child_matches(old_children, candidate["children"])
    used = {old_index for old_index in selected if old_index is not None}

    current_order = [child["node_id"] for child in old_children]
    for old_index in range(len(old_children) - 1, -1, -1):
        if old_index in used:
            continue
        old_child = old_children[old_index]
        current_index = current_order.index(old_child["node_id"])
        operations.append(
            {
                "op": "RemoveChild",
                "parent_id": previous["node_id"],
                "child_id": old_child["node_id"],
                "index": current_index,
            }
        )
        current_order.pop(current_index)
        delete_subtree(old_child, operations)

    next_children = []
    for new_index, (child_candidate, old_index) in enumerate(zip(candidate["children"], selected, strict=True)):
        if old_index is None:
            next_child = create_subtree(child_candidate, allocator, operations)
            operations.append(
                {
                    "op": "InsertChild",
                    "parent_id": previous["node_id"],
                    "child_id": next_child["node_id"],
                    "index": new_index,
                }
            )
            current_order.insert(new_index, next_child["node_id"])
        else:
            next_child = reconcile_node(old_children[old_index], child_candidate, allocator, operations)
            current_index = current_order.index(next_child["node_id"])
            if current_index != new_index:
                operations.append(
                    {
                        "op": "MoveChild",
                        "parent_id": previous["node_id"],
                        "child_id": next_child["node_id"],
                        "from": current_index,
                        "to": new_index,
                    }
                )
                current_order.insert(new_index, current_order.pop(current_index))
        next_children.append(next_child)

    return {
        "node_id": previous["node_id"],
        "kind": candidate["kind"],
        "key": candidate["key"],
        "properties": copy.deepcopy(candidate["properties"]),
        "children": next_children,
    }


def execute(fixture: dict[str, Any], schemas: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Execute one fixture with the deterministic reference oracle."""
    limits = validate_transaction(fixture)
    previous = fixture["previous"]
    if previous is not None:
        max_node_id = validate_committed_tree(previous, limits, schemas)
        if fixture["allocator_next_id"] <= max_node_id:
            raise ContractViolation(
                "INVALID_ALLOCATOR_STATE", "next node ID must exceed every committed identity"
            )
        if previous["revision"] != fixture["base_revision"]:
            raise ContractViolation("STALE_REVISION", "previous revision does not match base revision")
    validate_candidate(fixture["candidate"], limits, schemas)
    allocator = Allocator(fixture["allocator_next_id"])
    operations: list[dict[str, Any]] = []
    if previous is None:
        root = create_subtree(fixture["candidate"], allocator, operations)
    else:
        if not matches(previous["root"], fixture["candidate"]):
            raise ContractViolation("ROOT_REPLACEMENT_UNSUPPORTED", "v1 cannot replace a surface root")
        root = reconcile_node(previous["root"], fixture["candidate"], allocator, operations)
    result = {
        "result": "batch",
        "operations": operations,
        "committed": {"revision": fixture["target_revision"], "root": root},
        "next_node_id": allocator.next_id,
    }
    if len(operations) > limits["max_operations"]:
        raise ContractViolation(
            "OPERATION_COUNT_LIMIT", f"batch contains over {limits['max_operations']} operations"
        )
    return result


