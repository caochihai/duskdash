"""Report request/read/review use cases; JSON remains the source artifact."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from app.compat import UTC
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.services.access import require_permission
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike


class ReportRepositoryLike(Protocol):
    async def create(
        self,
        *,
        report_id: UUID,
        analysis_case_id: UUID,
        report_type: str,
        actor_id: UUID,
        outbox_id: UUID,
        correlation_id: UUID,
        event: Mapping[str, Any],
        headers: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    async def get(self, report_id: UUID) -> Mapping[str, Any] | None: ...

    async def claims(self, report_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def review(
        self,
        report_id: UUID,
        *,
        reviewer_id: UUID,
        status: str,
        review_note: str | None,
    ) -> Mapping[str, Any] | None: ...


class StorageLike(Protocol):
    async def create_presigned_get(
        self,
        bucket: str,
        key: str,
        *,
        expires_in_seconds: int | None = None,
        version_id: str | None = None,
    ) -> Any: ...


class ReportService:
    def __init__(
        self,
        repository: ReportRepositoryLike,
        storage: StorageLike,
        *,
        presigned_ttl_seconds: int = 600,
        audit: AuditService | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._presigned_ttl_seconds = presigned_ttl_seconds
        self._audit = audit

    async def request(
        self,
        principal: PrincipalLike,
        analysis_case_id: UUID,
        *,
        report_type: str,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "report:generate")
        report_id = uuid4()
        outbox_id = uuid4()
        correlation_id = request_id or uuid4()
        event = {
            "event_id": str(outbox_id),
            "event_type": "report.generation.requested",
            "event_version": 1,
            "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "producer": "bank-api",
            "correlation_id": str(correlation_id),
            "causation_id": None,
            "partition_key": str(report_id),
            "actor": {"type": "EMPLOYEE", "id": str(principal.employee_id)},
            "resource": {"type": "REPORT", "id": str(report_id)},
            "payload": {"analysis_case_id": str(analysis_case_id), "report_type": report_type},
            "metadata": {
                "trace_id": str(correlation_id),
                "schema": "report.generation.requested.v1",
            },
        }
        row = await self._repository.create(
            report_id=report_id,
            analysis_case_id=analysis_case_id,
            report_type=report_type,
            actor_id=principal.employee_id,
            outbox_id=outbox_id,
            correlation_id=correlation_id,
            event=event,
            headers={"topic": "bank.report.commands.v1"},
        )
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="REPORT_GENERATION_REQUESTED",
                resource_type="REPORT",
                resource_id=report_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=correlation_id,
                metadata={"analysis_case_id": analysis_case_id, "requested": True},
            )
        return row

    async def get(self, principal: PrincipalLike, report_id: UUID) -> Mapping[str, Any]:
        require_permission(principal, "report:read")
        row = await self._repository.get(report_id)
        if row is None:
            raise LookupError("Report was not found or is outside the authorized scope")
        return row

    async def claims(
        self, principal: PrincipalLike, report_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        await self.get(principal, report_id)
        return await self._repository.claims(report_id)

    async def review(
        self,
        principal: PrincipalLike,
        report_id: UUID,
        *,
        status: str,
        review_note: str | None,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "report:review")
        if status not in {"REVIEWED", "CHANGES_REQUESTED"}:
            raise ValueError("status must be REVIEWED or CHANGES_REQUESTED")
        row = await self._repository.review(
            report_id,
            reviewer_id=principal.employee_id,
            status=status,
            review_note=review_note,
        )
        if row is None:
            raise LookupError("Report was not found or is outside the authorized scope")
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="REPORT_REVIEWED",
                resource_type="REPORT",
                resource_id=report_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={"status": status},
            )
        return row

    async def download_url(
        self, principal: PrincipalLike, report_id: UUID
    ) -> Mapping[str, Any]:
        require_permission(principal, "report:export")
        row = await self.get(principal, report_id)
        if not row.get("object_key"):
            raise RuntimeError("Report PDF has not been generated")
        presigned = await self._storage.create_presigned_get(
            "generated-reports",
            str(row["object_key"]),
            expires_in_seconds=self._presigned_ttl_seconds,
            version_id=row.get("object_version_id"),
        )
        return {"url": presigned.url, "expires_in": presigned.expires_in_seconds}
