"""Durable job, step and replayable event persistence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_all, fetch_one, insert_sql, require_fields

_JOB_COLUMNS = frozenset(
    {
        "id",
        "job_type",
        "resource_type",
        "resource_id",
        "status",
        "progress_percent",
        "current_step",
        "correlation_id",
        "requested_by",
        "priority",
        "attempt_count",
        "max_attempts",
        "scheduled_at",
        "started_at",
        "completed_at",
        "error_code",
        "error_message_safe",
        "result_reference_type",
        "result_reference_id",
        "created_at",
        "updated_at",
        "version",
    }
)
_STEP_COLUMNS = frozenset(
    {
        "id",
        "job_id",
        "step_code",
        "step_order",
        "status",
        "progress_percent",
        "attempt_count",
        "started_at",
        "completed_at",
        "error_code",
        "error_message_safe",
        "created_at",
        "updated_at",
    }
)


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, values: Mapping[str, Any]) -> Record:
        require_fields(
            values,
            ("id", "job_type", "resource_type", "resource_id", "status", "correlation_id", "created_at", "updated_at"),
        )
        row = await execute_returning(
            self.session,
            insert_sql("integration.background_job", values, _JOB_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Background job insert returned no row")
        return row

    async def create_step(self, values: Mapping[str, Any]) -> Record:
        require_fields(values, ("id", "job_id", "step_code", "step_order", "status", "created_at", "updated_at"))
        row = await execute_returning(
            self.session,
            insert_sql("integration.background_job_step", values, _STEP_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Background job step insert returned no row")
        return row

    async def get(self, job_id: UUID, *, employee_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT bj.* FROM integration.background_job AS bj
            WHERE bj.id = :job_id AND (
                bj.requested_by = :employee_id OR identity.current_is_admin()
                OR (bj.resource_type = 'CUSTOMER'
                    AND identity.can_access_customer(identity.current_employee_id(), bj.resource_id))
                OR (bj.resource_type = 'LOAN_APPLICATION'
                    AND identity.can_access_loan(identity.current_employee_id(), bj.resource_id))
                OR (bj.resource_type = 'DOCUMENT_VERSION' AND EXISTS (
                    SELECT 1 FROM document.document_version AS dv WHERE dv.id = bj.resource_id
                ))
                OR (bj.resource_type = 'ANALYSIS_CASE' AND EXISTS (
                    SELECT 1 FROM ai.analysis_case AS ac WHERE ac.id = bj.resource_id
                ))
                OR (bj.resource_type = 'REPORT' AND EXISTS (
                    SELECT 1 FROM ai.report AS r WHERE r.id = bj.resource_id
                ))
            )
            """,
            {"job_id": job_id, "employee_id": employee_id},
        )

    async def steps(self, job_id: UUID, *, employee_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT js.* FROM integration.background_job AS bj
            JOIN integration.background_job_step AS js ON js.job_id = bj.id
            WHERE bj.id = :job_id AND (
                bj.requested_by = :employee_id OR identity.current_is_admin()
                OR (bj.resource_type = 'LOAN_APPLICATION'
                    AND identity.can_access_loan(identity.current_employee_id(), bj.resource_id))
                OR (bj.resource_type = 'DOCUMENT_VERSION' AND EXISTS (
                    SELECT 1 FROM document.document_version AS dv WHERE dv.id = bj.resource_id
                ))
                OR (bj.resource_type = 'ANALYSIS_CASE' AND EXISTS (
                    SELECT 1 FROM ai.analysis_case AS ac WHERE ac.id = bj.resource_id
                ))
                OR (bj.resource_type = 'REPORT' AND EXISTS (
                    SELECT 1 FROM ai.report AS r WHERE r.id = bj.resource_id
                ))
            )
            ORDER BY js.step_order, js.id
            """,
            {"job_id": job_id, "employee_id": employee_id},
        )

    async def events(
        self,
        job_id: UUID,
        *,
        employee_id: UUID,
        after_sequence: int = 0,
    ) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT je.* FROM integration.background_job AS bj
            JOIN integration.job_event AS je ON je.job_id = bj.id
            WHERE bj.id = :job_id AND je.sequence_number > :after_sequence
              AND (
                bj.requested_by = :employee_id OR identity.current_is_admin()
                OR (bj.resource_type = 'LOAN_APPLICATION'
                    AND identity.can_access_loan(identity.current_employee_id(), bj.resource_id))
                OR (bj.resource_type = 'DOCUMENT_VERSION' AND EXISTS (
                    SELECT 1 FROM document.document_version AS dv WHERE dv.id = bj.resource_id
                ))
                OR (bj.resource_type = 'ANALYSIS_CASE' AND EXISTS (
                    SELECT 1 FROM ai.analysis_case AS ac WHERE ac.id = bj.resource_id
                ))
                OR (bj.resource_type = 'REPORT' AND EXISTS (
                    SELECT 1 FROM ai.report AS r WHERE r.id = bj.resource_id
                ))
              )
            ORDER BY je.sequence_number, je.id
            """,
            {"job_id": job_id, "employee_id": employee_id, "after_sequence": after_sequence},
        )

    async def append_event(
        self,
        job_id: UUID,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> Record | None:
        """Append one event with per-job transaction-level serialization."""
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:job_id AS text), 0))"),
            {"job_id": job_id},
        )
        return await execute_returning(
            self.session,
            """
            INSERT INTO integration.job_event (
                job_id, event_type, sequence_number, payload, created_at
            )
            SELECT :job_id, :event_type,
                   COALESCE(max(sequence_number), -1) + 1,
                   CAST(:payload AS jsonb), CURRENT_TIMESTAMP
            FROM integration.job_event WHERE job_id = :job_id
            RETURNING *
            """,
            {"job_id": job_id, "event_type": event_type, "payload": dict(payload)},
        )
