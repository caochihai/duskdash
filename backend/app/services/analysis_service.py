"""Analysis request, retry, and authorized read use cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.services.access import require_permission
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike


class AnalysisRepositoryLike(Protocol):
    async def create(
        self,
        *,
        analysis_case_id: UUID,
        job_id: UUID,
        outbox_id: UUID,
        customer_id: UUID,
        loan_application_id: UUID,
        objective: str,
        actor_id: UUID,
        correlation_id: UUID,
        event: Mapping[str, Any],
        headers: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    async def get(self, analysis_case_id: UUID) -> Mapping[str, Any] | None: ...

    async def tasks(self, analysis_case_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def findings(self, analysis_case_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def events(self, analysis_case_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def retry(
        self,
        analysis_case_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: UUID,
        outbox_id: UUID,
        event: Mapping[str, Any],
        headers: Mapping[str, Any],
    ) -> Mapping[str, Any] | None: ...


class AnalysisService:
    def __init__(self, repository: AnalysisRepositoryLike, audit: AuditService | None = None) -> None:
        self._repository = repository
        self._audit = audit

    async def request(
        self,
        principal: PrincipalLike,
        *,
        customer_id: UUID,
        loan_application_id: UUID,
        objective: str,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:analyze")
        if not objective.strip() or len(objective) > 2000:
            raise ValueError("objective must contain 1 to 2000 characters")
        analysis_case_id = uuid4()
        job_id = uuid4()
        outbox_id = uuid4()
        correlation_id = request_id or uuid4()
        event = self._event(
            event_id=outbox_id,
            analysis_case_id=analysis_case_id,
            job_id=job_id,
            actor_id=principal.employee_id,
            correlation_id=correlation_id,
            causation_id=None,
        )
        result = await self._repository.create(
            analysis_case_id=analysis_case_id,
            job_id=job_id,
            outbox_id=outbox_id,
            customer_id=customer_id,
            loan_application_id=loan_application_id,
            objective=objective.strip(),
            actor_id=principal.employee_id,
            correlation_id=correlation_id,
            event=event,
            headers={"topic": "bank.analysis.commands.v1"},
        )
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="ANALYSIS_REQUESTED",
                resource_type="ANALYSIS_CASE",
                resource_id=analysis_case_id,
                customer_id=customer_id,
                loan_application_id=loan_application_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=correlation_id,
                metadata={"job_id": job_id},
            )
        return result

    async def get(self, principal: PrincipalLike, analysis_case_id: UUID) -> Mapping[str, Any]:
        require_permission(principal, "loan:read")
        row = await self._repository.get(analysis_case_id)
        if row is None:
            raise LookupError("Analysis case was not found or is outside the authorized scope")
        return row

    async def tasks(
        self, principal: PrincipalLike, analysis_case_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        await self.get(principal, analysis_case_id)
        return await self._repository.tasks(analysis_case_id)

    async def findings(
        self, principal: PrincipalLike, analysis_case_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        await self.get(principal, analysis_case_id)
        return await self._repository.findings(analysis_case_id)

    async def events(
        self, principal: PrincipalLike, analysis_case_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        await self.get(principal, analysis_case_id)
        return await self._repository.events(analysis_case_id)

    async def retry(
        self,
        principal: PrincipalLike,
        analysis_case_id: UUID,
        *,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:analyze")
        current = await self.get(principal, analysis_case_id)
        if str(current["status"]) not in {"FAILED", "NEEDS_INFORMATION"}:
            raise ValueError("Only failed or information-blocked analyses can be retried")
        outbox_id = uuid4()
        correlation_id = request_id or uuid4()
        event = self._event(
            event_id=outbox_id,
            analysis_case_id=analysis_case_id,
            job_id=UUID(str(current["job_id"])),
            actor_id=principal.employee_id,
            correlation_id=correlation_id,
            causation_id=None,
        )
        result = await self._repository.retry(
            analysis_case_id,
            actor_id=principal.employee_id,
            correlation_id=correlation_id,
            outbox_id=outbox_id,
            event=event,
            headers={"topic": "bank.analysis.commands.v1"},
        )
        if result is None:
            raise RuntimeError("Analysis retry conflicted with another update")
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="ANALYSIS_RETRIED",
                resource_type="ANALYSIS_CASE",
                resource_id=analysis_case_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=correlation_id,
            )
        return result

    @staticmethod
    def _event(
        *,
        event_id: UUID,
        analysis_case_id: UUID,
        job_id: UUID,
        actor_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
    ) -> Mapping[str, Any]:
        return {
            "event_id": str(event_id),
            "event_type": "analysis.requested",
            "event_version": 1,
            "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "producer": "bank-api",
            "correlation_id": str(correlation_id),
            "causation_id": str(causation_id) if causation_id else None,
            "partition_key": str(analysis_case_id),
            "actor": {"type": "EMPLOYEE", "id": str(actor_id)},
            "resource": {"type": "ANALYSIS_CASE", "id": str(analysis_case_id)},
            "payload": {"job_id": str(job_id)},
            "metadata": {"trace_id": str(correlation_id), "schema": "analysis.requested.v1"},
        }

