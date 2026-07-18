"""Checklist helper preserving policy-derived requirements."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from app.services.access import require_permission
from app.services.protocols import PrincipalLike


class ChecklistRepositoryLike(Protocol):
    async def checklist(self, loan_application_id: UUID) -> Sequence[Mapping[str, Any]]: ...


class ChecklistService:
    def __init__(self, repository: ChecklistRepositoryLike) -> None:
        self._repository = repository

    async def get(
        self, principal: PrincipalLike, loan_application_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "loan:read")
        return await self._repository.checklist(loan_application_id)
