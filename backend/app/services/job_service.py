"""Durable background-job reads used by REST and SSE reconnect."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from app.services.protocols import PrincipalLike


class JobRepositoryLike(Protocol):
    async def get(self, job_id: UUID, *, employee_id: UUID) -> Mapping[str, Any] | None: ...

    async def steps(self, job_id: UUID, *, employee_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def events(
        self, job_id: UUID, *, employee_id: UUID, after_sequence: int = 0
    ) -> Sequence[Mapping[str, Any]]: ...


class JobService:
    def __init__(self, repository: JobRepositoryLike) -> None:
        self._repository = repository

    async def get(self, principal: PrincipalLike, job_id: UUID) -> Mapping[str, Any]:
        row = await self._repository.get(job_id, employee_id=principal.employee_id)
        if row is None:
            raise LookupError("Job was not found or is outside the authorized scope")
        return row

    async def steps(
        self, principal: PrincipalLike, job_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        await self.get(principal, job_id)
        return await self._repository.steps(job_id, employee_id=principal.employee_id)

    async def events(
        self, principal: PrincipalLike, job_id: UUID, *, after_sequence: int = 0
    ) -> Sequence[Mapping[str, Any]]:
        await self.get(principal, job_id)
        return await self._repository.events(
            job_id, employee_id=principal.employee_id, after_sequence=max(after_sequence, 0)
        )

