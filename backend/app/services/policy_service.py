"""Effective-dated policy retrieval without model-supplied legal knowledge."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import UUID

from app.services.access import require_permission
from app.services.protocols import PrincipalLike


class PolicyRepositoryLike(Protocol):
    async def list(self, *, as_of: date) -> Sequence[Mapping[str, Any]]: ...

    async def search(
        self, *, query: str, as_of: date, limit: int
    ) -> Sequence[Mapping[str, Any]]: ...

    async def get_clause(self, clause_id: UUID, *, as_of: date) -> Mapping[str, Any] | None: ...


class PolicyService:
    def __init__(self, repository: PolicyRepositoryLike) -> None:
        self._repository = repository

    async def list(
        self, principal: PrincipalLike, *, as_of: date | None = None
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "policy:read")
        return await self._repository.list(as_of=as_of or datetime.now(UTC).date())

    async def search(
        self,
        principal: PrincipalLike,
        *,
        query: str,
        as_of: date | None = None,
        limit: int = 20,
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "policy:read")
        if len(query.strip()) < 2:
            raise ValueError("Policy search query must contain at least two characters")
        return await self._repository.search(
            query=query.strip(),
            as_of=as_of or datetime.now(UTC).date(),
            limit=min(max(limit, 1), 100),
        )

    async def clause(
        self, principal: PrincipalLike, clause_id: UUID, *, as_of: date | None = None
    ) -> Mapping[str, Any]:
        require_permission(principal, "policy:read")
        row = await self._repository.get_clause(
            clause_id, as_of=as_of or datetime.now(UTC).date()
        )
        if row is None:
            raise LookupError("Effective policy clause was not found")
        return row
