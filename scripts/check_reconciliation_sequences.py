#!/usr/bin/env python3
"""Run deterministic generated reconciliation sequences and invariant checks."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

if __package__:
    from .deterministic_random import StableRandom
    from .reconciliation_batch_model import verify_batch_result
    from .reconciliation_oracle import execute
    from .reconciliation_validation import load_component_schemas
else:
    from deterministic_random import StableRandom
    from reconciliation_batch_model import verify_batch_result
    from reconciliation_oracle import execute
    from reconciliation_validation import load_component_schemas

SEEDS = (7, 19, 41, 73, 101, 149, 211, 307)
STEPS_PER_SEED = 25


class SequenceInvariantError(Exception):
    """Raised when a generated valid sequence violates a runtime invariant."""


def _properties(kind: str, rng: StableRandom, revision: int) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    if kind == "Text" and rng.chance(0.85):
        properties["1"] = {"type": "string", "value": f"text-{revision}-{rng.index(16)}"}
    if rng.chance(0.35):
        properties["2"] = {"type": "bool", "value": bool(rng.index(2))}
    if kind == "View" and rng.chance(0.25):
        properties["3"] = {"type": "i64", "value": rng.index(9) - 4}
    if rng.chance(0.4):
        properties["4"] = {"type": "f64", "value": rng.index(11) / 10}
    return properties


def _new_child(
    rng: StableRandom, next_key: list[int], revision: int, depth: int
) -> dict[str, Any]:
    kind = "View" if depth < 2 and rng.chance(0.45) else "Text"
    key = f"node-{next_key[0]}"
    next_key[0] += 1
    children = []
    if kind == "View" and depth < 2 and rng.chance(0.35):
        children.append(_new_child(rng, next_key, revision, depth + 1))
    return {
        "kind": kind,
        "key": key,
        "properties": _properties(kind, rng, revision),
        "children": children,
    }


def _evolve(
    previous: dict[str, Any],
    rng: StableRandom,
    next_key: list[int],
    revision: int,
    depth: int = 0,
) -> dict[str, Any]:
    node = copy.deepcopy(previous)
    node["properties"] = _properties(node["kind"], rng, revision)
    evolved_children = []
    for old_child in node["children"]:
        if rng.chance(0.22):
            continue
        child = copy.deepcopy(old_child)
        if rng.chance(0.14):
            child["kind"] = "Text" if child["kind"] == "View" else "View"
            child["children"] = []
            child["properties"] = _properties(child["kind"], rng, revision)
        elif child["kind"] == "View":
            child = _evolve(child, rng, next_key, revision, depth + 1)
        else:
            child["properties"] = _properties("Text", rng, revision)
        evolved_children.append(child)

    if depth < 2:
        additions = rng.index(3)
        for _ in range(min(additions, 5 - len(evolved_children))):
            evolved_children.append(_new_child(rng, next_key, revision, depth + 1))
    rng.shuffle(evolved_children)
    node["children"] = evolved_children
    return node


def _collect_ids(node: dict[str, Any], identities: set[int]) -> None:
    node_id = node["node_id"]
    if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id <= 0:
        raise SequenceInvariantError(f"invalid committed identity {node_id!r}")
    if node_id in identities:
        raise SequenceInvariantError(f"duplicate committed identity {node_id}")
    identities.add(node_id)
    for child in node["children"]:
        _collect_ids(child, identities)


def _assert_preserved(previous: dict[str, Any], committed: dict[str, Any]) -> None:
    if previous["kind"] == committed["kind"] and previous["key"] == committed["key"]:
        if previous["node_id"] != committed["node_id"]:
            raise SequenceInvariantError("matched node identity changed")
    old_children = {(child["key"], child["kind"]): child for child in previous["children"]}
    for child in committed["children"]:
        old_child = old_children.get((child["key"], child["kind"]))
        if old_child is not None:
            _assert_preserved(old_child, child)


def _initial_candidate() -> dict[str, Any]:
    return {"kind": "View", "key": None, "properties": {}, "children": []}


def run_campaign(
    seeds: tuple[int, ...] = SEEDS, steps_per_seed: int = STEPS_PER_SEED
) -> dict[str, Any]:
    """Run fixed-seed stateful sequences and return reproducible campaign metrics."""
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "contracts"
        / "reconciliation"
        / "v1"
        / "schema"
        / "components.json"
    )
    schemas = load_component_schemas(schema_path)
    digest = hashlib.sha256()
    operation_count = 0
    operation_types: dict[str, int] = {}
    created_count = 0

    for seed in seeds:
        rng = StableRandom(seed)
        previous = None
        candidate = _initial_candidate()
        next_key = [1]
        next_node_id = 1
        ever_created: set[int] = set()

        for revision in range(1, steps_per_seed + 1):
            if revision > 1:
                candidate = _evolve(candidate, rng, next_key, revision)
            fixture = {
                "contract_version": 1,
                "name": f"generated-{seed}-{revision}",
                "base_revision": revision - 1,
                "target_revision": revision,
                "allocator_next_id": next_node_id,
                "previous": previous,
                "candidate": candidate,
                "expected": {},
            }
            result = execute(fixture, schemas)
            verify_batch_result(previous, result)
            committed = result["committed"]
            if committed["revision"] != revision:
                raise SequenceInvariantError("committed revision does not match the transaction")
            if previous is not None:
                _assert_preserved(previous["root"], committed["root"])

            current_ids: set[int] = set()
            _collect_ids(committed["root"], current_ids)
            created = {
                operation["node_id"]
                for operation in result["operations"]
                if operation["op"] == "Create"
            }
            if created.intersection(ever_created):
                raise SequenceInvariantError("a runtime identity was reused within a surface")
            ever_created.update(created)
            next_node_id = result["next_node_id"]
            if next_node_id <= max(current_ids):
                raise SequenceInvariantError("allocator did not advance past committed identities")

            operation_count += len(result["operations"])
            for operation in result["operations"]:
                name = operation["op"]
                operation_types[name] = operation_types.get(name, 0) + 1
            created_count += len(created)
            digest.update(json.dumps(result, sort_keys=True, separators=(",", ":")).encode())
            previous = committed

    return {
        "seeds": len(seeds),
        "steps_per_seed": steps_per_seed,
        "transitions": len(seeds) * steps_per_seed,
        "operations": operation_count,
        "operation_types": dict(sorted(operation_types.items())),
        "created_nodes": created_count,
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    """Execute the full deterministic campaign and print its measured summary."""
    print(json.dumps(run_campaign(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
