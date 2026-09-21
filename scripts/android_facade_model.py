"""Executable lifecycle model for the public Android surface facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MAX_KOTLIN_LONG = (1 << 63) - 1


class AndroidFacadeViolation(Exception):
    """Raised with a stable contract code for an invalid facade transition."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class FacadeState:
    """Minimal state owned by one future Kotlin `RmfSurfaceHost` instance."""

    state: str = "NEW"
    handle: tuple[int, int] | None = None
    last_sequence: int = 0
    failure: str | None = None
    queued_from: str | None = None

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-compatible observable state."""
        handle = None
        if self.handle is not None:
            handle = {"surface_id": self.handle[0], "generation": self.handle[1]}
        return {
            "state": self.state,
            "handle": handle,
            "last_sequence": self.last_sequence,
            "failure": self.failure,
            "queued_from": self.queued_from,
        }


def _effect(effect_type: str, **fields: int) -> dict[str, Any]:
    return {"type": effect_type, **fields}


def _main(action: dict[str, Any]) -> None:
    if action.get("caller_thread") != "main":
        raise AndroidFacadeViolation("WRONG_THREAD")


def _positive(value: object, code: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
        or value > MAX_KOTLIN_LONG
    ):
        raise AndroidFacadeViolation(code)
    return value


def _handle(action: dict[str, Any]) -> tuple[int, int]:
    return (
        _positive(action.get("surface_id"), "INVALID_HANDLE"),
        _positive(action.get("generation"), "INVALID_HANDLE"),
    )


def apply_action(model: FacadeState, action: dict[str, Any]) -> dict[str, Any]:
    """Apply one closed facade action and return exactly one observable effect."""
    action_type = action.get("type")
    if action_type == "request_create":
        if set(action) != {"type", "caller_thread"} or model.state != "NEW":
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        if action["caller_thread"] == "main":
            model.state = "CREATING"
            return _effect("CALL_NATIVE_CREATE")
        if action["caller_thread"] == "worker":
            model.state = "CREATE_QUEUED"
            return _effect("POST_CREATE_TO_MAIN")
        raise AndroidFacadeViolation("WRONG_THREAD")

    if action_type == "main_drain_create":
        if set(action) != {"type", "caller_thread"}:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        _main(action)
        if model.state == "CREATE_QUEUED":
            model.state = "CREATING"
            return _effect("CALL_NATIVE_CREATE")
        if model.state == "CLOSE_QUEUED" and model.queued_from == "CREATE_QUEUED":
            model.state = "CLOSED"
            model.queued_from = None
            return _effect("CANCEL_QUEUED_CREATE")
        if model.state == "CLOSED":
            return _effect("IGNORE_CANCELLED_TASK")
        raise AndroidFacadeViolation("INVALID_TRANSITION")

    if action_type == "native_create_succeeded":
        if set(action) != {"type", "caller_thread", "surface_id", "generation"}:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        _main(action)
        handle = _handle(action)
        if model.state == "CREATING":
            model.state = "ACTIVE"
            model.handle = handle
            return _effect("NONE")
        if model.state == "CLOSE_PENDING_CREATE":
            model.state = "CLOSING"
            model.handle = handle
            return _effect(
                "CALL_NATIVE_DISPOSE", surface_id=handle[0], generation=handle[1]
            )
        if model.state == "CLOSE_QUEUED" and model.queued_from == "CREATING":
            model.state = "CLOSING"
            model.queued_from = None
            model.handle = handle
            return _effect(
                "CALL_NATIVE_DISPOSE", surface_id=handle[0], generation=handle[1]
            )
        raise AndroidFacadeViolation("INVALID_TRANSITION")

    if action_type == "native_create_failed":
        if set(action) != {"type", "caller_thread", "reason"}:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        _main(action)
        valid_state = model.state in {"CREATING", "CLOSE_PENDING_CREATE"} or (
            model.state == "CLOSE_QUEUED" and model.queued_from == "CREATING"
        )
        if not valid_state:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        if action["reason"] not in {"HOST_UNAVAILABLE", "HOST_INTERNAL"}:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        model.state = "FAILED"
        model.queued_from = None
        model.failure = f"CREATE_{action['reason']}"
        return _effect("NONE")

    if action_type == "request_close":
        if set(action) != {"type", "caller_thread"}:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        if action["caller_thread"] not in {"main", "worker"}:
            raise AndroidFacadeViolation("WRONG_THREAD")
        if action["caller_thread"] == "worker":
            if model.state in {"NEW", "CREATE_QUEUED", "CREATING", "ACTIVE"}:
                model.queued_from = model.state
                model.state = "CLOSE_QUEUED"
                return _effect("POST_CLOSE_TO_MAIN")
            if model.state in {
                "CLOSE_QUEUED",
                "CLOSE_PENDING_CREATE",
                "CLOSING",
                "CLOSED",
                "FAILED",
            }:
                return _effect("NONE")
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        if model.state == "NEW":
            model.state = "CLOSED"
            return _effect("NONE")
        if model.state == "CREATE_QUEUED":
            model.state = "CLOSED"
            return _effect("CANCEL_QUEUED_CREATE")
        if model.state == "CREATING":
            model.state = "CLOSE_PENDING_CREATE"
            return _effect("NONE")
        if model.state == "ACTIVE":
            if model.handle is None:
                raise AndroidFacadeViolation("INVALID_HANDLE")
            model.state = "CLOSING"
            return _effect(
                "CALL_NATIVE_DISPOSE",
                surface_id=model.handle[0],
                generation=model.handle[1],
            )
        if model.state in {"CLOSE_QUEUED", "CLOSE_PENDING_CREATE", "CLOSING", "CLOSED", "FAILED"}:
            return _effect("NONE")
        raise AndroidFacadeViolation("INVALID_TRANSITION")

    if action_type == "main_drain_close":
        if set(action) != {"type", "caller_thread"}:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        _main(action)
        if model.state == "CLOSE_QUEUED":
            queued_from = model.queued_from
            model.queued_from = None
            if queued_from == "NEW":
                model.state = "CLOSED"
                return _effect("NONE")
            if queued_from == "CREATE_QUEUED":
                model.state = "CLOSED"
                return _effect("CANCEL_QUEUED_CREATE")
            if queued_from == "CREATING":
                model.state = "CLOSE_PENDING_CREATE"
                return _effect("NONE")
            if queued_from == "ACTIVE" and model.handle is not None:
                model.state = "CLOSING"
                return _effect(
                    "CALL_NATIVE_DISPOSE",
                    surface_id=model.handle[0],
                    generation=model.handle[1],
                )
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        if model.state in {"CLOSING", "CLOSED", "FAILED"}:
            return _effect("IGNORE_CANCELLED_TASK")
        raise AndroidFacadeViolation("INVALID_TRANSITION")

    if action_type in {"native_dispose_succeeded", "native_dispose_failed"}:
        expected_fields = {"type", "caller_thread"}
        if action_type == "native_dispose_failed":
            expected_fields.add("reason")
        if set(action) != expected_fields:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        _main(action)
        if model.state != "CLOSING":
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        if action_type == "native_dispose_succeeded":
            model.handle = None
            model.state = "CLOSED"
        else:
            if action["reason"] not in {"HOST_UNAVAILABLE", "HOST_INTERNAL"}:
                raise AndroidFacadeViolation("INVALID_TRANSITION")
            model.handle = None
            model.state = "FAILED"
            model.failure = f"DISPOSE_{action['reason']}"
        return _effect("NONE")

    if action_type == "native_callback":
        fields = {"type", "caller_thread", "surface_id", "generation", "sequence"}
        if set(action) != fields:
            raise AndroidFacadeViolation("INVALID_TRANSITION")
        _main(action)
        handle = _handle(action)
        sequence = _positive(action["sequence"], "INVALID_SEQUENCE")
        if model.state != "ACTIVE" or handle != model.handle or sequence <= model.last_sequence:
            return _effect("DROP_CALLBACK")
        model.last_sequence = sequence
        return _effect("DELIVER_CALLBACK", sequence=sequence)

    raise AndroidFacadeViolation("INVALID_TRANSITION")
