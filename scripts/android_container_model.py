"""Executable ownership model for an Android ViewGroup host adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast


MAX_KOTLIN_LONG = (1 << 63) - 1


class AndroidContainerViolation(Exception):
    """Raised with a stable contract code for a rejected operation."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class Binding:
    """Current exclusive claim on one container."""

    host_id: int
    mount_id: int
    state: str = "RESERVED"
    root_id: int | None = None


@dataclass
class ContainerRegistry:
    """Safe observable state owned by the future Android adapter."""

    next_mount_id: int = 1
    bindings: dict[int, Binding] | None = None
    retired_roots: set[int] | None = None

    def __post_init__(self) -> None:
        if self.bindings is None:
            self.bindings = {}
        if self.retired_roots is None:
            self.retired_roots = set()

    def snapshot(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible state."""
        bindings = cast(dict[int, Binding], self.bindings)
        retired_roots = cast(set[int], self.retired_roots)
        return {
            "next_mount_id": self.next_mount_id,
            "bindings": {
                str(container_id): {
                    "host_id": binding.host_id,
                    "mount_id": binding.mount_id,
                    "state": binding.state,
                    "root_id": binding.root_id,
                }
                for container_id, binding in sorted(bindings.items())
            },
            "retired_roots": sorted(retired_roots),
        }


def _effect(effect_type: str, **fields: int) -> dict[str, Any]:
    return {"type": effect_type, **fields}


def _positive(value: object) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
        or value > MAX_KOTLIN_LONG
    ):
        raise AndroidContainerViolation("INVALID_ID")
    return value


def _main(action: dict[str, Any]) -> None:
    if action.get("caller_thread") != "main":
        raise AndroidContainerViolation("WRONG_THREAD")


def _identity(action: dict[str, Any]) -> tuple[int, int, int]:
    return (
        _positive(action.get("container_id")),
        _positive(action.get("host_id")),
        _positive(action.get("mount_id")),
    )


def apply_action(model: ContainerRegistry, action: dict[str, Any]) -> dict[str, Any]:
    """Apply one closed container action and return one observable effect."""
    bindings = cast(dict[int, Binding], model.bindings)
    retired_roots = cast(set[int], model.retired_roots)
    action_type = action.get("type")
    if action_type == "claim":
        if set(action) != {"type", "caller_thread", "container_id", "host_id"}:
            raise AndroidContainerViolation("INVALID_ID")
        _main(action)
        container_id = _positive(action["container_id"])
        host_id = _positive(action["host_id"])
        if container_id in bindings:
            raise AndroidContainerViolation("CONTAINER_ALREADY_OWNED")
        if model.next_mount_id > MAX_KOTLIN_LONG:
            raise AndroidContainerViolation("MOUNT_ID_EXHAUSTED")
        mount_id = model.next_mount_id
        model.next_mount_id += 1
        bindings[container_id] = Binding(host_id, mount_id)
        return _effect(
            "ADD_ROOT",
            container_id=container_id,
            host_id=host_id,
            mount_id=mount_id,
        )

    if action_type in {"attach_succeeded", "attach_failed", "release"}:
        expected = {"type", "caller_thread", "container_id", "host_id", "mount_id"}
        if action_type == "attach_succeeded":
            expected.add("root_id")
        if set(action) != expected:
            raise AndroidContainerViolation("INVALID_ID")
        _main(action)
        container_id, host_id, mount_id = _identity(action)
        binding = bindings.get(container_id)
        current = binding is not None and (
            binding.host_id == host_id and binding.mount_id == mount_id
        )

        if action_type == "release":
            if not current:
                return _effect("DROP_STALE_RELEASE")
            del bindings[container_id]
            if binding.state == "RESERVED":
                return _effect("CANCEL_ATTACH", mount_id=mount_id)
            if binding.root_id is None:
                raise AndroidContainerViolation("ROOT_NOT_DETACHED")
            retired_roots.add(binding.root_id)
            return _effect(
                "REMOVE_ROOT",
                container_id=container_id,
                root_id=binding.root_id,
                mount_id=mount_id,
            )

        if action_type == "attach_failed":
            if not current or binding.state != "RESERVED":
                return _effect("DROP_STALE_RESULT")
            del bindings[container_id]
            return _effect("NONE")

        root_id = _positive(action["root_id"])
        active_roots = {
            candidate.root_id
            for candidate in bindings.values()
            if candidate.root_id is not None
        }
        if not current or binding.state != "RESERVED":
            if root_id in active_roots:
                return _effect("DROP_STALE_RESULT")
            retired_roots.add(root_id)
            return _effect("REMOVE_STALE_ROOT", root_id=root_id, mount_id=mount_id)
        if root_id in active_roots or root_id in retired_roots:
            raise AndroidContainerViolation("ROOT_NOT_DETACHED")
        binding.state = "ATTACHED"
        binding.root_id = root_id
        return _effect("NONE")

    raise AndroidContainerViolation("INVALID_ID")
