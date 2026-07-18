"""Explicit state transitions for human-controlled business workflows."""

from __future__ import annotations

from collections.abc import Mapping

LOAN_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "DRAFT": frozenset({"DOCUMENT_COLLECTION", "WITHDRAWN"}),
    "DOCUMENT_COLLECTION": frozenset({"UNDER_ANALYSIS", "NEEDS_INFORMATION", "WITHDRAWN"}),
    "UNDER_ANALYSIS": frozenset({"NEEDS_INFORMATION", "READY_FOR_REVIEW", "WITHDRAWN"}),
    "NEEDS_INFORMATION": frozenset({"DOCUMENT_COLLECTION", "UNDER_ANALYSIS", "WITHDRAWN"}),
    "READY_FOR_REVIEW": frozenset({"SUBMITTED_FOR_APPROVAL", "NEEDS_INFORMATION", "WITHDRAWN"}),
    "SUBMITTED_FOR_APPROVAL": frozenset(
        {"APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED", "NEEDS_INFORMATION"}
    ),
    "APPROVED": frozenset(),
    "APPROVED_WITH_CONDITIONS": frozenset(),
    "REJECTED": frozenset(),
    "WITHDRAWN": frozenset(),
}

UPLOAD_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "CREATED": frozenset({"UPLOADING", "UPLOADED", "EXPIRED", "FAILED"}),
    "UPLOADING": frozenset({"UPLOADED", "EXPIRED", "FAILED"}),
    "UPLOADED": frozenset({"VERIFYING", "FAILED"}),
    "VERIFYING": frozenset({"COMPLETED", "FAILED"}),
    "COMPLETED": frozenset(),
    "EXPIRED": frozenset(),
    "FAILED": frozenset(),
}


def can_transition(current: str, target: str, transitions: Mapping[str, frozenset[str]]) -> bool:
    """Return whether a transition is explicitly allowed.

    Treating a same-state request as idempotent is useful for retry-safe APIs.
    Unknown states are denied rather than silently accepted.
    """

    if current == target:
        return current in transitions
    return target in transitions.get(current, frozenset())


def require_transition(current: str, target: str, transitions: Mapping[str, frozenset[str]]) -> None:
    if not can_transition(current, target, transitions):
        msg = f"Transition {current} -> {target} is not allowed"
        raise ValueError(msg)

