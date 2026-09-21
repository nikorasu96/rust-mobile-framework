"""Independent host-tree model for validating reconciliation mutation batches."""

from __future__ import annotations

import copy
from typing import Any


class BatchApplicationError(Exception):
    """Raised when a mutation batch violates the host model contract."""


def host_projection(node: dict[str, Any]) -> dict[str, Any]:
    """Return the committed fields observable through the host mutation protocol."""
    return {
        "node_id": node["node_id"],
        "kind": node["kind"],
        "properties": copy.deepcopy(node["properties"]),
        "children": [host_projection(child) for child in node["children"]],
    }


def _seed_tree(
    node: dict[str, Any],
    nodes: dict[int, dict[str, Any]],
    parents: dict[int, int | None],
    parent_id: int | None,
) -> None:
    node_id = node["node_id"]
    if node_id in nodes:
        raise BatchApplicationError(f"duplicate seed node {node_id}")
    nodes[node_id] = {
        "node_id": node_id,
        "kind": node["kind"],
        "properties": copy.deepcopy(node["properties"]),
        "children": [child["node_id"] for child in node["children"]],
    }
    parents[node_id] = parent_id
    for child in node["children"]:
        _seed_tree(child, nodes, parents, node_id)


def _require_node(nodes: dict[int, dict[str, Any]], node_id: object) -> dict[str, Any]:
    if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id not in nodes:
        raise BatchApplicationError(f"unknown node {node_id!r}")
    return nodes[node_id]


def _require_index(index: object, upper_bound: int, *, allow_end: bool) -> int:
    if not isinstance(index, int) or isinstance(index, bool):
        raise BatchApplicationError(f"invalid child index {index!r}")
    maximum = upper_bound if allow_end else upper_bound - 1
    if index < 0 or index > maximum:
        raise BatchApplicationError(f"child index {index} outside 0..{maximum}")
    return index


def _apply_operation(
    operation: dict[str, Any],
    nodes: dict[int, dict[str, Any]],
    parents: dict[int, int | None],
    root_id: int | None,
) -> int | None:
    name = operation.get("op")
    if name == "Create":
        node_id = operation.get("node_id")
        if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id <= 0:
            raise BatchApplicationError(f"invalid created node ID {node_id!r}")
        if node_id in nodes:
            raise BatchApplicationError(f"created node {node_id} already exists")
        kind = operation.get("kind")
        if not isinstance(kind, str) or not kind:
            raise BatchApplicationError("created node kind must be a non-empty string")
        nodes[node_id] = {"node_id": node_id, "kind": kind, "properties": {}, "children": []}
        parents[node_id] = None
        return node_id if root_id is None else root_id

    if name == "UpdateProperties":
        node = _require_node(nodes, operation.get("node_id"))
        set_properties = operation.get("set")
        removed = operation.get("remove")
        if not isinstance(set_properties, dict) or not isinstance(removed, list):
            raise BatchApplicationError("invalid property update payload")
        if len(removed) != len(set(removed)) or any(not isinstance(key, str) for key in removed):
            raise BatchApplicationError("removed properties must be unique strings")
        if set(set_properties).intersection(removed):
            raise BatchApplicationError("a property cannot be set and removed together")
        for key in removed:
            if key not in node["properties"]:
                raise BatchApplicationError(f"cannot remove absent property {key}")
            del node["properties"][key]
        node["properties"].update(copy.deepcopy(set_properties))
        return root_id

    if name == "InsertChild":
        parent = _require_node(nodes, operation.get("parent_id"))
        child = _require_node(nodes, operation.get("child_id"))
        child_id = child["node_id"]
        if parents[child_id] is not None or child_id == root_id:
            raise BatchApplicationError(f"node {child_id} is already attached")
        index = _require_index(operation.get("index"), len(parent["children"]), allow_end=True)
        parent["children"].insert(index, child_id)
        parents[child_id] = parent["node_id"]
        return root_id

    if name == "MoveChild":
        parent = _require_node(nodes, operation.get("parent_id"))
        child = _require_node(nodes, operation.get("child_id"))
        source = _require_index(operation.get("from"), len(parent["children"]), allow_end=False)
        target = _require_index(operation.get("to"), len(parent["children"]), allow_end=False)
        if parent["children"][source] != child["node_id"] or parents[child["node_id"]] != parent["node_id"]:
            raise BatchApplicationError("move source does not identify the attached child")
        parent["children"].insert(target, parent["children"].pop(source))
        return root_id

    if name == "RemoveChild":
        parent = _require_node(nodes, operation.get("parent_id"))
        child = _require_node(nodes, operation.get("child_id"))
        index = _require_index(operation.get("index"), len(parent["children"]), allow_end=False)
        if parent["children"][index] != child["node_id"] or parents[child["node_id"]] != parent["node_id"]:
            raise BatchApplicationError("remove index does not identify the attached child")
        parent["children"].pop(index)
        parents[child["node_id"]] = None
        return root_id

    if name == "Delete":
        node = _require_node(nodes, operation.get("node_id"))
        node_id = node["node_id"]
        if node_id == root_id:
            raise BatchApplicationError("surface root cannot be deleted")
        if parents[node_id] is not None or node["children"]:
            raise BatchApplicationError(f"node {node_id} must be detached and empty before deletion")
        del nodes[node_id]
        del parents[node_id]
        return root_id

    raise BatchApplicationError(f"unknown mutation operation {name!r}")


def _materialize(
    node_id: int, nodes: dict[int, dict[str, Any]], visited: set[int]
) -> dict[str, Any]:
    if node_id in visited:
        raise BatchApplicationError(f"node {node_id} is reachable more than once")
    visited.add(node_id)
    node = nodes[node_id]
    return {
        "node_id": node_id,
        "kind": node["kind"],
        "properties": copy.deepcopy(node["properties"]),
        "children": [_materialize(child_id, nodes, visited) for child_id in node["children"]],
    }


def apply_batch(previous: dict[str, Any] | None, operations: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply a batch to an independent host model and return its projected tree."""
    nodes: dict[int, dict[str, Any]] = {}
    parents: dict[int, int | None] = {}
    root_id = None
    if previous is not None:
        root_id = previous["root"]["node_id"]
        _seed_tree(previous["root"], nodes, parents, None)
    for operation in operations:
        if not isinstance(operation, dict):
            raise BatchApplicationError("each mutation operation must be an object")
        root_id = _apply_operation(operation, nodes, parents, root_id)
    if root_id is None or root_id not in nodes:
        raise BatchApplicationError("batch did not leave a surface root")
    visited: set[int] = set()
    projected = _materialize(root_id, nodes, visited)
    if visited != set(nodes):
        detached = sorted(set(nodes) - visited)
        raise BatchApplicationError(f"batch left detached nodes {detached}")
    return projected


def verify_batch_result(previous: dict[str, Any] | None, result: dict[str, Any]) -> None:
    """Require an independently applied batch to reproduce the committed host view."""
    if result.get("result") != "batch":
        raise BatchApplicationError("only successful batch results can be applied")
    operations = result.get("operations")
    committed = result.get("committed")
    if not isinstance(operations, list) or not isinstance(committed, dict) or "root" not in committed:
        raise BatchApplicationError("malformed successful batch result")
    actual = apply_batch(previous, operations)
    expected = host_projection(committed["root"])
    if actual != expected:
        raise BatchApplicationError("applied host tree differs from committed host projection")
