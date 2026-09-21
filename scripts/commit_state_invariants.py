"""Safety invariants shared by generated commit-state model checks."""

from __future__ import annotations

from typing import Any


class StateInvariantError(Exception):
    """Raised when a commit-state transition violates runtime safety."""


def confirmed_revision(state: dict[str, Any]) -> int:
    """Return the last revision confirmed by the host for any surface state."""
    if state["state"] == "applying":
        return state["base_revision"]
    return state["revision"]


def verify_transition(
    previous: dict[str, Any],
    action: dict[str, Any],
    current: dict[str, Any],
    output: dict[str, Any],
) -> None:
    """Assert promotion, failure isolation and recovery invariants."""
    previous_revision = confirmed_revision(previous)
    current_revision = confirmed_revision(current)
    promoted = output["result"] == "commit_promoted"
    expected_promotion = previous["state"] == "applying" and action["op"] == "host_applied"
    if promoted != expected_promotion:
        raise StateInvariantError("promotion did not exactly match host success")
    if promoted:
        if current_revision != previous_revision + 1 or current["state"] != "ready":
            raise StateInvariantError("host success did not atomically promote one revision")
    elif current_revision != previous_revision:
        raise StateInvariantError("revision changed without confirmed host success")

    if previous["state"] == "failed":
        if current["state"] not in {"failed", "remounting"}:
            raise StateInvariantError("failed state escaped without starting remount")
        if current["state"] == "remounting" and action["op"] != "begin_remount":
            raise StateInvariantError("failed state entered remounting through the wrong action")
    if previous["state"] == "remounting" and current["state"] == "ready":
        if action["op"] != "remount_succeeded" or output["result"] != "surface_restored":
            raise StateInvariantError("remounting escaped without remount success")
    if output["result"] in {"batch_discarded", "rejected", "recovery_required"}:
        if current_revision != previous_revision:
            raise StateInvariantError("non-success outcome changed confirmed revision")

    allowed_states = {
        "ready": {"ready", "applying"},
        "applying": {"applying", "ready", "failed"},
        "failed": {"failed", "remounting"},
        "remounting": {"remounting", "ready", "failed"},
    }
    if current["state"] not in allowed_states[previous["state"]]:
        raise StateInvariantError("state transition crossed a forbidden boundary")
