"""Safety invariants shared by generated surface lifecycle checks."""

from __future__ import annotations

from typing import Any

if __package__:
    from .check_surface_lifecycle_fixtures import MAX_U64
else:
    from check_surface_lifecycle_fixtures import MAX_U64


class LifecycleInvariantError(Exception):
    """Raised when a lifecycle transition violates registry safety."""


def verify_transition(
    previous: dict[str, Any],
    action: dict[str, Any],
    current: dict[str, Any],
    output: dict[str, Any],
) -> None:
    """Assert exact-handle routing, allocator progress and surface isolation."""
    before = previous["active"]
    operation = action["op"]
    if operation == "create":
        duplicate = any(handle["surface_id"] == action["surface_id"] for handle in before)
        if duplicate:
            expected = {"result": "rejected", "code": "SURFACE_ALREADY_ACTIVE"}
            if output != expected or current != previous:
                raise LifecycleInvariantError("duplicate creation changed registry state")
            return
        allocator = previous["allocator"]
        if allocator["status"] == "exhausted":
            expected = {"result": "rejected", "code": "GENERATION_EXHAUSTED"}
            if output != expected or current != previous:
                raise LifecycleInvariantError("exhausted creation changed registry state")
            return
        expected_handle = {
            "surface_id": action["surface_id"],
            "generation": allocator["next"],
        }
        if output != {"result": "created", "handle": expected_handle}:
            raise LifecycleInvariantError("creation did not use the next generation")
        expected_active = sorted(before + [expected_handle], key=lambda item: item["surface_id"])
        expected_allocator = (
            {"status": "exhausted"}
            if allocator["next"] == MAX_U64
            else {"status": "available", "next": allocator["next"] + 1}
        )
        if current != {"allocator": expected_allocator, "active": expected_active}:
            raise LifecycleInvariantError("creation changed an unrelated surface or allocator")
        return

    handle = action["handle"]
    is_active = handle in before
    if not is_active:
        expected = {"result": "rejected", "code": "STALE_SURFACE_HANDLE"}
        if output != expected or current != previous:
            raise LifecycleInvariantError("stale handle changed registry state")
        return
    if operation == "callback":
        if output != {"result": "callback_accepted", "handle": handle} or current != previous:
            raise LifecycleInvariantError("valid callback changed lifecycle state")
        return
    expected_active = [item for item in before if item != handle]
    expected_state = {"allocator": previous["allocator"], "active": expected_active}
    if output != {"result": "disposed", "handle": handle} or current != expected_state:
        raise LifecycleInvariantError("disposal changed the wrong surface")
