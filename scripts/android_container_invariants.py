"""Reusable safety invariants for Android container ownership."""

from __future__ import annotations

from typing import Any, cast

try:
    from scripts.android_container_model import MAX_KOTLIN_LONG, Binding, ContainerRegistry
except ModuleNotFoundError:
    from android_container_model import MAX_KOTLIN_LONG, Binding, ContainerRegistry


class AndroidContainerInvariantError(Exception):
    """Raised when container state or a transition violates the contract."""


def _positive(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 < value <= MAX_KOTLIN_LONG
    )


def validate_state(model: ContainerRegistry) -> None:
    """Reject malformed bindings, reused roots and allocator discontinuity."""
    if (
        not isinstance(model.next_mount_id, int)
        or isinstance(model.next_mount_id, bool)
        or not 0 < model.next_mount_id <= MAX_KOTLIN_LONG + 1
    ):
        raise AndroidContainerInvariantError("invalid mount allocator")
    if not isinstance(model.bindings, dict) or not isinstance(model.retired_roots, set):
        raise AndroidContainerInvariantError("invalid registry collections")
    bindings = cast(dict[int, Binding], model.bindings)
    retired = cast(set[int], model.retired_roots)
    if any(not _positive(root_id) for root_id in retired):
        raise AndroidContainerInvariantError("invalid retired root")

    mount_ids: set[int] = set()
    active_roots: set[int] = set()
    for container_id, binding in bindings.items():
        if not _positive(container_id) or not isinstance(binding, Binding):
            raise AndroidContainerInvariantError("invalid container binding")
        if not _positive(binding.host_id) or not _positive(binding.mount_id):
            raise AndroidContainerInvariantError("invalid binding identity")
        if binding.mount_id >= model.next_mount_id or binding.mount_id in mount_ids:
            raise AndroidContainerInvariantError("mount ID was reused or escaped allocator")
        mount_ids.add(binding.mount_id)
        if binding.state == "RESERVED":
            if binding.root_id is not None:
                raise AndroidContainerInvariantError("reserved binding owns a root")
        elif binding.state == "ATTACHED":
            if not _positive(binding.root_id):
                raise AndroidContainerInvariantError("attached binding has no valid root")
            root_id = cast(int, binding.root_id)
            if root_id in active_roots or root_id in retired:
                raise AndroidContainerInvariantError("root has multiple or stale ownership")
            active_roots.add(root_id)
        else:
            raise AndroidContainerInvariantError("unknown binding state")


def verify_transition(
    previous: ContainerRegistry,
    action: dict[str, Any],
    current: ContainerRegistry,
    effect: dict[str, Any] | None,
    error: str | None,
) -> None:
    """Check atomic rejection, exact-root cleanup and stale-work isolation."""
    before = previous.snapshot()
    after = current.snapshot()
    if error is not None:
        if effect is not None or after != before:
            raise AndroidContainerInvariantError("rejected action mutated container state")
        return
    if effect is None:
        raise AndroidContainerInvariantError("accepted action produced no effect")
    effect_type = effect.get("type")
    if action.get("caller_thread") != "main":
        raise AndroidContainerInvariantError("hierarchy work escaped main thread")

    previous_bindings = before["bindings"]
    current_bindings = after["bindings"]
    target = str(action.get("container_id"))
    for container in set(previous_bindings) | set(current_bindings):
        if container != target and previous_bindings.get(container) != current_bindings.get(container):
            raise AndroidContainerInvariantError("operation changed an unrelated container")
    if not set(before["retired_roots"]).issubset(after["retired_roots"]):
        raise AndroidContainerInvariantError("retired root ownership was forgotten")
    if effect_type in {"DROP_STALE_RESULT", "DROP_STALE_RELEASE"} and after != before:
        raise AndroidContainerInvariantError("dropped stale work changed registry state")
    if effect_type == "ADD_ROOT":
        container = str(effect.get("container_id"))
        binding = current_bindings.get(container)
        if (
            binding is None
            or container in previous_bindings
            or binding["state"] != "RESERVED"
            or binding["host_id"] != effect.get("host_id")
            or binding["mount_id"] != effect.get("mount_id")
            or after["next_mount_id"] != before["next_mount_id"] + 1
            or after["retired_roots"] != before["retired_roots"]
        ):
            raise AndroidContainerInvariantError("claim did not reserve one fresh mount")
    elif after["next_mount_id"] != before["next_mount_id"]:
        raise AndroidContainerInvariantError("non-claim changed mount allocator")

    if effect_type == "CANCEL_ATTACH":
        container = str(action.get("container_id"))
        binding = previous_bindings.get(container)
        if (
            binding is None
            or binding["state"] != "RESERVED"
            or binding["mount_id"] != effect.get("mount_id")
            or container in current_bindings
            or after["retired_roots"] != before["retired_roots"]
        ):
            raise AndroidContainerInvariantError("cancel did not remove exact reservation")
    elif effect_type == "REMOVE_ROOT":
        container = str(effect.get("container_id"))
        binding = previous_bindings.get(container)
        root_id = effect.get("root_id")
        if (
            binding is None
            or binding["state"] != "ATTACHED"
            or binding["root_id"] != root_id
            or binding["mount_id"] != effect.get("mount_id")
            or container in current_bindings
            or root_id not in after["retired_roots"]
        ):
            raise AndroidContainerInvariantError("detach did not remove exact owned root")
    elif effect_type == "REMOVE_STALE_ROOT":
        if (
            current_bindings != previous_bindings
            or effect.get("root_id") not in after["retired_roots"]
        ):
            raise AndroidContainerInvariantError("stale cleanup changed a current binding")
    elif effect_type == "NONE":
        binding_before = previous_bindings.get(target)
        binding_after = current_bindings.get(target)
        if action.get("type") == "attach_succeeded":
            if (
                binding_before is None
                or binding_before["state"] != "RESERVED"
                or binding_after is None
                or binding_after["state"] != "ATTACHED"
                or binding_after["root_id"] != action.get("root_id")
            ):
                raise AndroidContainerInvariantError("attach confirmation was not exact")
        elif action.get("type") == "attach_failed":
            if (
                binding_before is None
                or binding_before["state"] != "RESERVED"
                or target in current_bindings
            ):
                raise AndroidContainerInvariantError("attach failure retained its reservation")
        else:
            raise AndroidContainerInvariantError("unexpected no-op effect")
        if after["retired_roots"] != before["retired_roots"]:
            raise AndroidContainerInvariantError("current attach result changed retired roots")
