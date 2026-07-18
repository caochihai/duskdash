"""Finding and evidence reads with ownership enforced by repository joins."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from app.services.access import require_permission
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike


class EvidenceRepositoryLike(Protocol):
    async def get_finding(self, finding_id: UUID) -> Mapping[str, Any] | None: ...

    async def get_evidence(self, finding_id: UUID) -> Sequence[Mapping[str, Any]]: ...


class EvidenceService:
    def __init__(self, repository: EvidenceRepositoryLike, audit: AuditService | None = None) -> None:
        self._repository = repository
        self._audit = audit

    async def finding(
        self, principal: PrincipalLike, finding_id: UUID, *, request_id: UUID | None = None
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:read")
        row = await self._repository.get_finding(finding_id)
        if row is None:
            raise LookupError("Finding was not found or is outside the authorized scope")
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="FINDING_VIEWED",
                resource_type="FINDING",
                resource_id=finding_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
            )
        return row

    async def evidence(
        self, principal: PrincipalLike, finding_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        await self.finding(principal, finding_id)
        return await self._repository.get_evidence(finding_id)
