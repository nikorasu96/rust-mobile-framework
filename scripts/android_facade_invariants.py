"""Safety invariants shared by Android facade state-space checks."""

from __future__ import annotations

from typing import Any

try:
    from scripts.android_facade_model import MAX_KOTLIN_LONG, FacadeState
except ModuleNotFoundError:
    from android_facade_model import MAX_KOTLIN_LONG, FacadeState


class AndroidFacadeInvariantError(Exception):
    """Raised when a facade state or transition violates a safety property."""


def validate_state(model: FacadeState, registered_states: set[str]) -> None:
    """Reject internally inconsistent states, handles and failure markers."""
    if model.state not in registered_states:
        raise AndroidFacadeInvariantError("unregistered state")
    if (
        not isinstance(model.last_sequence, int)
        or isinstance(model.last_sequence, bool)
        or not 0 <= model.last_sequence <= MAX_KOTLIN_LONG
    ):
        raise AndroidFacadeInvariantError("invalid callback sequence state")

    handle_states = {"ACTIVE", "CLOSING"}
    queued_active = model.state == "CLOSE_QUEUED" and model.queued_from == "ACTIVE"
    must_have_handle = model.state in handle_states or queued_active
    if must_have_handle != (model.handle is not None):
        raise AndroidFacadeInvariantError("handle does not match lifecycle state")
    if model.handle is not None:
        if not isinstance(model.handle, tuple) or len(model.handle) != 2 or any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 < value <= MAX_KOTLIN_LONG
            for value in model.handle
        ):
            raise AndroidFacadeInvariantError("invalid stored handle")

    if model.state == "CLOSE_QUEUED":
        if model.queued_from not in {"NEW", "CREATE_QUEUED", "CREATING", "ACTIVE"}:
            raise AndroidFacadeInvariantError("invalid queued close origin")
    elif model.queued_from is not None:
        raise AndroidFacadeInvariantError("queued close origin escaped its state")

    if model.state == "FAILED":
        if model.failure not in {
            "CREATE_HOST_UNAVAILABLE",
            "CREATE_HOST_INTERNAL",
            "DISPOSE_HOST_UNAVAILABLE",
            "DISPOSE_HOST_INTERNAL",
        }:
            raise AndroidFacadeInvariantError("failed state has no registered reason")
        if model.failure.startswith("CREATE_") and model.last_sequence != 0:
            raise AndroidFacadeInvariantError("create failure retained a callback sequence")
    elif model.failure is not None:
        raise AndroidFacadeInvariantError("failure escaped terminal state")


def verify_transition(
    previous: FacadeState,
    action: dict[str, Any],
    current: FacadeState,
    effect: dict[str, Any] | None,
    error: str | None,
    *,
    close_was_requested: bool,
    create_calls: int,
    dispose_calls: int,
) -> None:
    """Assert mutation atomicity, main-thread effects and lifecycle cardinality."""
    before = previous.snapshot()
    after = current.snapshot()
    if error is not None:
        if effect is not None or after != before:
            raise AndroidFacadeInvariantError("rejected action changed facade state")
        return
    if effect is None:
        raise AndroidFacadeInvariantError("accepted action produced no effect")
    effect_type = effect["type"]

    if create_calls > 1 or dispose_calls > 1:
        raise AndroidFacadeInvariantError("native lifecycle effect repeated")
    if effect_type in {"CALL_NATIVE_CREATE", "CALL_NATIVE_DISPOSE"}:
        if action.get("caller_thread") != "main":
            raise AndroidFacadeInvariantError("native work escaped the main thread")
    if effect_type == "CALL_NATIVE_DISPOSE":
        handle = (effect.get("surface_id"), effect.get("generation"))
        if current.handle != handle:
            raise AndroidFacadeInvariantError("dispose did not use the owned complete handle")
    if effect_type == "DELIVER_CALLBACK":
        action_handle = (action.get("surface_id"), action.get("generation"))
        if (
            close_was_requested
            or previous.state != "ACTIVE"
            or previous.handle != action_handle
            or effect.get("sequence") != action.get("sequence")
            or current.last_sequence <= previous.last_sequence
        ):
            raise AndroidFacadeInvariantError("unsafe callback delivery")
    if effect_type == "DROP_CALLBACK" and after != before:
        raise AndroidFacadeInvariantError("dropped callback changed facade state")
    if previous.state in {"CLOSED", "FAILED"} and after != before:
        raise AndroidFacadeInvariantError("terminal facade state changed")
