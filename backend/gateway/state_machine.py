"""Authoritative case-state transition rules.

Routes and orchestration code must use this module instead of assigning a case
state directly.  Keeping the rules in one place prevents invalid transitions
such as committing a draft case or reopening a completed case.
"""
from __future__ import annotations

from common.schemas import CaseState


class InvalidStateTransition(ValueError):
    """Raised when a requested case state change is not allowed."""


ALLOWED_TRANSITIONS: dict[CaseState, set[CaseState]] = {
    CaseState.DRAFT: {CaseState.IN_ANALYSIS},
    CaseState.IN_ANALYSIS: {
        CaseState.NEEDS_INFO,
        CaseState.PENDING_APPROVAL,
        CaseState.REJECTED,
        CaseState.ESCALATED,
    },
    CaseState.NEEDS_INFO: {CaseState.IN_ANALYSIS, CaseState.REJECTED, CaseState.ESCALATED},
    CaseState.PENDING_APPROVAL: {CaseState.EXECUTING, CaseState.REJECTED, CaseState.ESCALATED},
    # A failed precondition invalidates approval and returns the case to analysis.
    CaseState.EXECUTING: {CaseState.COMPLETED, CaseState.IN_ANALYSIS, CaseState.ESCALATED},
    CaseState.COMPLETED: set(),
    CaseState.REJECTED: set(),
    CaseState.ESCALATED: set(),
}


def validate_transition(current: str | CaseState, target: str | CaseState) -> None:
    """Validate a state transition; a no-op is permitted for idempotent callers."""
    try:
        current_state = current if isinstance(current, CaseState) else CaseState(current)
        target_state = target if isinstance(target, CaseState) else CaseState(target)
    except ValueError as exc:
        raise InvalidStateTransition(f"Unknown case state: {current!r} -> {target!r}") from exc

    if current_state == target_state:
        return
    if target_state not in ALLOWED_TRANSITIONS[current_state]:
        raise InvalidStateTransition(
            f"Invalid case transition: {current_state.value} -> {target_state.value}"
        )
