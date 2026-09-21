"""Dependency-free surface lifecycle model shared by contracts and adapters."""

from __future__ import annotations

import copy
from typing import Any


MAX_U64 = 2**64 - 1
ACTION_FIELDS = {
    "create": {"op", "surface_id"},
    "dispose": {"op", "handle"},
    "callback": {"op", "handle"},
}


class SurfaceLifecycleViolation(Exception):
    """Raised when data is outside the closed lifecycle v1 contract."""


def _positive_u64(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= MAX_U64:
        raise SurfaceLifecycleViolation(f"{name} must be a positive u64")
    return value


def validate_handle(value: object) -> dict[str, int]:
    """Validate and copy a closed surface handle."""
    if not isinstance(value, dict) or set(value) != {"surface_id", "generation"}:
        raise SurfaceLifecycleViolation("invalid surface handle fields")
    return {
        "surface_id": _positive_u64(value["surface_id"], "surface_id"),
        "generation": _positive_u64(value["generation"], "generation"),
    }


def validate_state(value: object) -> dict[str, Any]:
    """Validate allocator and active handles, then return an owned state."""
    if not isinstance(value, dict) or set(value) != {"allocator", "active"}:
        raise SurfaceLifecycleViolation("invalid lifecycle state fields")
    allocator = value["allocator"]
    if not isinstance(allocator, dict) or allocator.get("status") not in {
        "available",
        "exhausted",
    }:
        raise SurfaceLifecycleViolation("invalid allocator state")
    expected = {"status", "next"} if allocator["status"] == "available" else {"status"}
    if set(allocator) != expected:
        raise SurfaceLifecycleViolation("invalid allocator fields")
    next_generation = None
    if allocator["status"] == "available":
        next_generation = _positive_u64(allocator["next"], "allocator.next")

    if not isinstance(value["active"], list):
        raise SurfaceLifecycleViolation("active handles must be a list")
    active = [validate_handle(handle) for handle in value["active"]]
    if active != sorted(active, key=lambda handle: handle["surface_id"]):
        raise SurfaceLifecycleViolation("active handles must be sorted by surface_id")
    surface_ids = [handle["surface_id"] for handle in active]
    generations = [handle["generation"] for handle in active]
    if len(surface_ids) != len(set(surface_ids)) or len(generations) != len(set(generations)):
        raise SurfaceLifecycleViolation("active handle identities must be unique")
    if next_generation is not None and any(item >= next_generation for item in generations):
        raise SurfaceLifecycleViolation("allocator must follow every assigned generation")
    return copy.deepcopy(value)


def _rejected(state: dict[str, Any], code: str) -> tuple[dict[str, Any], dict[str, str]]:
    return state, {"result": "rejected", "code": code}


def transition(
    state: dict[str, Any], action: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one validated lifecycle action without mutating the input state."""
    if not isinstance(action, dict) or action.get("op") not in ACTION_FIELDS:
        raise SurfaceLifecycleViolation("unknown lifecycle action")
    if set(action) != ACTION_FIELDS[action["op"]]:
        raise SurfaceLifecycleViolation(f"invalid fields for action {action['op']}")
    current = validate_state(state)
    operation = action["op"]

    if operation == "create":
        surface_id = _positive_u64(action["surface_id"], "surface_id")
        if any(handle["surface_id"] == surface_id for handle in current["active"]):
            return _rejected(current, "SURFACE_ALREADY_ACTIVE")
        allocator = current["allocator"]
        if allocator["status"] == "exhausted":
            return _rejected(current, "GENERATION_EXHAUSTED")
        generation = allocator["next"]
        handle = {"surface_id": surface_id, "generation": generation}
        current["active"].append(handle)
        current["active"].sort(key=lambda item: item["surface_id"])
        current["allocator"] = (
            {"status": "exhausted"}
            if generation == MAX_U64
            else {"status": "available", "next": generation + 1}
        )
        return current, {"result": "created", "handle": handle}

    handle = validate_handle(action["handle"])
    if handle not in current["active"]:
        return _rejected(current, "STALE_SURFACE_HANDLE")
    if operation == "dispose":
        current["active"].remove(handle)
        return current, {"result": "disposed", "handle": handle}
    return current, {"result": "callback_accepted", "handle": handle}
