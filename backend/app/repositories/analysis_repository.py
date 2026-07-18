"""Analysis case/task orchestration persistence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_all, fetch_one, insert_sql, require_fields

_CASE_COLUMNS = frozenset(
    {
        "id",
        "case_type",
        "customer_id",
        "loan_application_id",
        "conversation_id",
        "created_by",
        "status",
        "objective",
        "correlation_id",
        "created_at",
        "completed_at",
    }
)
_TASK_COLUMNS = frozenset(
    {
        "id",
        "analysis_case_id",
        "task_code",
        "agent_type",
        "objective",
        "status",
        "depends_on",
        "attempt_count",
        "started_at",
        "completed_at",
        "error_code",
        "created_at",
    }
)


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
    ) -> Record:
        now = datetime.now(UTC)
        values = {
            "id": analysis_case_id,
            "case_type": "LOAN_APPLICATION_ANALYSIS",
            "customer_id": customer_id,
            "loan_application_id": loan_application_id,
            "conversation_id": None,
            "created_by": actor_id,
            "status": "QUEUED",
            "objective": objective,
            "correlation_id": correlation_id,
            "created_at": now,
            "completed_at": None,
        }
        row = await execute_returning(
            self.session,
            insert_sql("ai.analysis_case", values, _CASE_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Analysis case insert returned no row")
        await execute_returning(
            self.session,
            """
            INSERT INTO integration.background_job (
                id, job_type, resource_type, resource_id, status,
                progress_percent, current_step, correlation_id, requested_by,
                priority, attempt_count, max_attempts, scheduled_at,
                created_at, updated_at, version
            ) VALUES (
                :job_id, 'LOAN_ANALYSIS', 'ANALYSIS_CASE', :case_id, 'QUEUED',
                0, 'AWAITING_PUBLICATION', :correlation_id, :actor_id,
                5, 0, 5, :now, :now, :now, 1
            ) RETURNING id
            """,
            {
                "job_id": job_id,
                "case_id": analysis_case_id,
                "correlation_id": correlation_id,
                "actor_id": actor_id,
                "now": now,
            },
        )
        await execute_returning(
            self.session,
            """
            INSERT INTO integration.event_outbox (
                id, aggregate_type, aggregate_id, event_type, event_version,
                partition_key, payload, headers, status, attempt_count,
                available_at, created_at
            ) VALUES (
                :outbox_id, 'ANALYSIS_CASE', :case_id, 'analysis.requested', 1,
                CAST(:case_id AS text), CAST(:event AS jsonb),
                CAST(:headers AS jsonb), 'PENDING', 0, :now, :now
            ) RETURNING id
            """,
            {
                "outbox_id": outbox_id,
                "case_id": analysis_case_id,
                "event": event,
                "headers": headers,
                "now": now,
            },
        )
        row["job_id"] = job_id
        row["outbox_id"] = outbox_id
        return row

    async def create_task(self, values: Mapping[str, Any]) -> Record:
        require_fields(
            values,
            ("id", "analysis_case_id", "task_code", "agent_type", "objective", "status", "created_at"),
        )
        row = await execute_returning(
            self.session,
            insert_sql("ai.analysis_task", values, _TASK_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Analysis task insert returned no row")
        return row

    async def get(self, analysis_case_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT ac.*, bj.id AS job_id, bj.status AS job_status,
                   bj.progress_percent, bj.current_step
            FROM ai.analysis_case AS ac
            LEFT JOIN integration.background_job AS bj
              ON bj.resource_type = 'ANALYSIS_CASE' AND bj.resource_id = ac.id
            WHERE ac.id = :case_id
            """,
            {"case_id": analysis_case_id},
        )

    async def tasks(self, analysis_case_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT at.* FROM ai.analysis_case AS ac
            JOIN ai.analysis_task AS at ON at.analysis_case_id = ac.id
            WHERE ac.id = :case_id
            ORDER BY at.created_at, at.task_code, at.id
            """,
            {"case_id": analysis_case_id},
        )

    async def findings(self, analysis_case_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT f.* FROM ai.analysis_case AS ac
            JOIN ai.finding AS f ON f.analysis_case_id = ac.id
            WHERE ac.id = :case_id
            ORDER BY f.severity DESC, f.created_at, f.id
            """,
            {"case_id": analysis_case_id},
        )

    async def events(self, analysis_case_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT je.* FROM ai.analysis_case AS ac
            JOIN integration.background_job AS bj
              ON bj.resource_type = 'ANALYSIS_CASE' AND bj.resource_id = ac.id
            JOIN integration.job_event AS je ON je.job_id = bj.id
            WHERE ac.id = :case_id
            ORDER BY je.sequence_number, je.id
            """,
            {"case_id": analysis_case_id},
        )

    async def retry(
        self,
        analysis_case_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: UUID,
        outbox_id: UUID,
        event: Mapping[str, Any],
        headers: Mapping[str, Any],
    ) -> Record | None:
        now = datetime.now(UTC)
        row = await execute_returning(
            self.session,
            """
            UPDATE ai.analysis_case
            SET status = 'QUEUED', completed_at = NULL
            WHERE id = :case_id AND status IN ('FAILED', 'NEEDS_INFORMATION')
            RETURNING *
            """,
            {"case_id": analysis_case_id},
        )
        if row is None:
            return None
        job = await execute_returning(
            self.session,
            """
            UPDATE integration.background_job
            SET status = 'QUEUED', progress_percent = 0,
                current_step = 'AWAITING_PUBLICATION',
                correlation_id = :correlation_id, requested_by = :actor_id,
                scheduled_at = :now, started_at = NULL, completed_at = NULL,
                error_code = NULL, error_message_safe = NULL,
                updated_at = :now, version = version + 1
            WHERE resource_type = 'ANALYSIS_CASE' AND resource_id = :case_id
            RETURNING id
            """,
            {
                "case_id": analysis_case_id,
                "correlation_id": correlation_id,
                "actor_id": actor_id,
                "now": now,
            },
        )
        if job is None:
            raise RuntimeError("Analysis background job is missing")
        await execute_returning(
            self.session,
            """
            INSERT INTO integration.event_outbox (
                id, aggregate_type, aggregate_id, event_type, event_version,
                partition_key, payload, headers, status, attempt_count,
                available_at, created_at
            ) VALUES (
                :outbox_id, 'ANALYSIS_CASE', :case_id, 'analysis.requested', 1,
                CAST(:case_id AS text), CAST(:event AS jsonb),
                CAST(:headers AS jsonb), 'PENDING', 0, :now, :now
            ) RETURNING id
            """,
            {
                "outbox_id": outbox_id,
                "case_id": analysis_case_id,
                "event": event,
                "headers": headers,
                "now": now,
            },
        )
        row["job_id"] = job["id"]
        row["outbox_id"] = outbox_id
        return row
