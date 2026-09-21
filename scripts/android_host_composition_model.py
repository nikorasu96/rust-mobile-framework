"""Composition model for the Android facade, container, and Rust surface lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from scripts.android_container_model import (
        AndroidContainerViolation,
        ContainerRegistry,
        apply_action as apply_container_action,
    )
    from scripts.android_facade_model import (
        MAX_KOTLIN_LONG,
        AndroidFacadeViolation,
        FacadeState,
        apply_action as apply_facade_action,
    )
    from scripts.surface_lifecycle_model import transition as surface_transition
except ModuleNotFoundError:
    from android_container_model import (
        AndroidContainerViolation,
        ContainerRegistry,
        apply_action as apply_container_action,
    )
    from android_facade_model import (
        MAX_KOTLIN_LONG,
        AndroidFacadeViolation,
        FacadeState,
        apply_action as apply_facade_action,
    )
    from surface_lifecycle_model import transition as surface_transition


ACTION_FIELDS = {
    "begin": {"type", "caller_thread", "container_id", "host_id", "surface_id", "root_id"},
    "native_create_succeeded": {"type", "caller_thread"},
    "native_create_failed": {"type", "caller_thread", "reason"},
    "close": {"type", "caller_thread"},
    "callback": {"type", "caller_thread", "surface_id", "generation", "sequence"},
}


class AndroidHostCompositionViolation(Exception):
    """Raised with a stable code when an orchestration action is malformed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class AndroidHostState:
    """State owned by one composed Android host adapter instance."""

    facade: FacadeState = field(default_factory=FacadeState)
    containers: ContainerRegistry = field(default_factory=ContainerRegistry)
    surfaces: dict[str, Any] = field(
        default_factory=lambda: {"allocator": {"status": "available", "next": 1}, "active": []}
    )
    container_id: int | None = None
    host_id: int | None = None
    surface_id: int | None = None
    root_id: int | None = None
    mount_id: int | None = None

    def snapshot(self) -> dict[str, Any]:
        """Return deterministic, JSON-compatible composite state."""
        return {
            "facade": self.facade.snapshot(),
            "containers": self.containers.snapshot(),
            "surfaces": self.surfaces,
            "identity": {
                "container_id": self.container_id,
                "host_id": self.host_id,
                "surface_id": self.surface_id,
                "root_id": self.root_id,
                "mount_id": self.mount_id,
            },
        }


def _outcome(outcome_type: str, **fields: str | int) -> dict[str, Any]:
    return {"type": outcome_type, **fields}


def _validate_action(action: dict[str, Any]) -> str:
    action_type = action.get("type")
    if action_type not in ACTION_FIELDS or set(action) != ACTION_FIELDS[action_type]:
        raise AndroidHostCompositionViolation("INVALID_ACTION")
    if action.get("caller_thread") != "main":
        raise AndroidHostCompositionViolation("WRONG_THREAD")
    return action_type


def _positive_id(value: object) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
        or value > MAX_KOTLIN_LONG
    ):
        raise AndroidHostCompositionViolation("INVALID_ID")
    return value


def _fail_creation(model: AndroidHostState, reason: str) -> None:
    if model.facade.state == "NEW":
        apply_facade_action(model.facade, {"type": "request_create", "caller_thread": "main"})
    apply_facade_action(
        model.facade,
        {"type": "native_create_failed", "caller_thread": "main", "reason": reason},
    )


def _release_owned_container(model: AndroidHostState) -> None:
    if model.mount_id is None:
        return
    if model.container_id is None or model.host_id is None:
        raise AndroidHostCompositionViolation("INTERNAL_INVARIANT")
    apply_container_action(
        model.containers,
        {
            "type": "release",
            "caller_thread": "main",
            "container_id": model.container_id,
            "host_id": model.host_id,
            "mount_id": model.mount_id,
        },
    )
    model.mount_id = None


def _dispose_surface(model: AndroidHostState, handle: dict[str, int]) -> None:
    next_state, result = surface_transition(
        model.surfaces, {"op": "dispose", "handle": handle}
    )
    if result["result"] != "disposed":
        raise AndroidHostCompositionViolation("INTERNAL_INVARIANT")
    model.surfaces = next_state


def _begin(model: AndroidHostState, action: dict[str, Any]) -> dict[str, Any]:
    if model.facade.state != "NEW":
        raise AndroidHostCompositionViolation("INVALID_TRANSITION")
    for field_name in ("container_id", "host_id", "surface_id", "root_id"):
        _positive_id(action[field_name])
    try:
        claim = apply_container_action(
            model.containers,
            {
                "type": "claim",
                "caller_thread": "main",
                "container_id": action["container_id"],
                "host_id": action["host_id"],
            },
        )
    except AndroidContainerViolation as error:
        if error.code in {"CONTAINER_ALREADY_OWNED", "MOUNT_ID_EXHAUSTED"}:
            _fail_creation(model, "HOST_UNAVAILABLE")
            return _outcome("START_FAILED", reason=error.code)
        raise AndroidHostCompositionViolation(error.code) from error

    model.container_id = action["container_id"]
    model.host_id = action["host_id"]
    model.surface_id = action["surface_id"]
    model.root_id = action["root_id"]
    model.mount_id = claim["mount_id"]
    try:
        apply_container_action(
            model.containers,
            {
                "type": "attach_succeeded",
                "caller_thread": "main",
                "container_id": model.container_id,
                "host_id": model.host_id,
                "mount_id": model.mount_id,
                "root_id": model.root_id,
            },
        )
    except AndroidContainerViolation as error:
        _release_owned_container(model)
        if error.code == "ROOT_NOT_DETACHED":
            _fail_creation(model, "HOST_UNAVAILABLE")
            return _outcome("START_FAILED", reason=error.code)
        raise AndroidHostCompositionViolation(error.code) from error

    effect = apply_facade_action(
        model.facade, {"type": "request_create", "caller_thread": "main"}
    )
    if effect["type"] != "CALL_NATIVE_CREATE":
        raise AndroidHostCompositionViolation("INTERNAL_INVARIANT")
    return _outcome("CREATE_REQUESTED", mount_id=model.mount_id)


def _native_create_succeeded(model: AndroidHostState) -> dict[str, Any]:
    if model.facade.state not in {"CREATING", "CLOSE_PENDING_CREATE"}:
        raise AndroidHostCompositionViolation("INVALID_TRANSITION")
    if model.surface_id is None:
        raise AndroidHostCompositionViolation("INVALID_TRANSITION")
    next_state, result = surface_transition(
        model.surfaces, {"op": "create", "surface_id": model.surface_id}
    )
    if result["result"] == "rejected":
        _fail_creation(model, "HOST_UNAVAILABLE")
        _release_owned_container(model)
        return _outcome("START_FAILED", reason=result["code"])

    model.surfaces = next_state
    handle = result["handle"]
    if handle["generation"] > MAX_KOTLIN_LONG:
        _dispose_surface(model, handle)
        _fail_creation(model, "HOST_UNAVAILABLE")
        _release_owned_container(model)
        return _outcome("START_FAILED", reason="HANDLE_OUT_OF_RANGE")
    effect = apply_facade_action(
        model.facade,
        {
            "type": "native_create_succeeded",
            "caller_thread": "main",
            "surface_id": handle["surface_id"],
            "generation": handle["generation"],
        },
    )
    if effect["type"] == "NONE":
        return _outcome("SURFACE_ACTIVE", generation=handle["generation"])
    if effect["type"] != "CALL_NATIVE_DISPOSE":
        raise AndroidHostCompositionViolation("INTERNAL_INVARIANT")
    _dispose_surface(model, handle)
    apply_facade_action(
        model.facade, {"type": "native_dispose_succeeded", "caller_thread": "main"}
    )
    return _outcome("LATE_SURFACE_DISPOSED", generation=handle["generation"])


def _close(model: AndroidHostState) -> dict[str, Any]:
    previous = model.facade.state
    effect = apply_facade_action(
        model.facade, {"type": "request_close", "caller_thread": "main"}
    )
    if previous == "CREATING":
        _release_owned_container(model)
        return _outcome("CLOSE_WAITING_NATIVE")
    if effect["type"] == "CALL_NATIVE_DISPOSE":
        handle = {"surface_id": effect["surface_id"], "generation": effect["generation"]}
        _dispose_surface(model, handle)
        _release_owned_container(model)
        apply_facade_action(
            model.facade, {"type": "native_dispose_succeeded", "caller_thread": "main"}
        )
        return _outcome("CLOSED")
    return _outcome("NONE")


def _callback(model: AndroidHostState, action: dict[str, Any]) -> dict[str, Any]:
    for field_name in ("surface_id", "generation", "sequence"):
        _positive_id(action[field_name])
    handle = {"surface_id": action["surface_id"], "generation": action["generation"]}
    _, result = surface_transition(model.surfaces, {"op": "callback", "handle": handle})
    if result["result"] != "callback_accepted":
        return _outcome("CALLBACK_DROPPED", reason=result["code"])
    effect = apply_facade_action(
        model.facade,
        {
            "type": "native_callback",
            "caller_thread": "main",
            "surface_id": action["surface_id"],
            "generation": action["generation"],
            "sequence": action["sequence"],
        },
    )
    if effect["type"] == "DELIVER_CALLBACK":
        return _outcome("CALLBACK_DELIVERED", sequence=effect["sequence"])
    return _outcome("CALLBACK_DROPPED", reason="FACADE_REJECTED")


def apply_action(model: AndroidHostState, action: dict[str, Any]) -> dict[str, Any]:
    """Apply one main-thread orchestration action to the composed host."""
    action_type = _validate_action(action)
    try:
        if action_type == "begin":
            return _begin(model, action)
        if action_type == "native_create_succeeded":
            return _native_create_succeeded(model)
        if action_type == "native_create_failed":
            effect = apply_facade_action(model.facade, action)
            if effect["type"] != "NONE":
                raise AndroidHostCompositionViolation("INTERNAL_INVARIANT")
            _release_owned_container(model)
            return _outcome("START_FAILED", reason=action["reason"])
        if action_type == "close":
            return _close(model)
        return _callback(model, action)
    except AndroidFacadeViolation as error:
        raise AndroidHostCompositionViolation(error.code) from error
