"""Structured report and claim persistence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from app.compat import UTC
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_all, fetch_one, insert_sql, require_fields

_REPORT_COLUMNS = frozenset(
    {
        "id",
        "analysis_case_id",
        "report_type",
        "status",
        "generated_by_agent_run_id",
        "reviewed_by",
        "approved_by",
        "version_number",
        "json_payload",
        "pdf_object_id",
        "created_at",
    }
)
_CLAIM_COLUMNS = frozenset(
    {
        "id",
        "report_id",
        "section",
        "claim_text",
        "claim_type",
        "confidence",
        "validation_status",
        "created_at",
    }
)


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
    ) -> Record:
        now = datetime.now(UTC)
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:case_id AS text), 1))"),
            {"case_id": analysis_case_id},
        )
        row = await execute_returning(
            self.session,
            """
            INSERT INTO ai.report (
                id, analysis_case_id, report_type, status,
                generated_by_agent_run_id, reviewed_by, approved_by,
                version_number, json_payload, pdf_object_id, created_at
            )
            SELECT :report_id, ac.id, :report_type, 'QUEUED',
                   NULL, NULL, NULL,
                   COALESCE((SELECT max(version_number) FROM ai.report
                             WHERE analysis_case_id = ac.id), 0) + 1,
                   '{}'::jsonb, NULL, :now
            FROM ai.analysis_case AS ac WHERE ac.id = :case_id
            RETURNING *
            """,
            {
                "report_id": report_id,
                "case_id": analysis_case_id,
                "report_type": report_type,
                "now": now,
            },
        )
        if row is None:
            raise LookupError("Analysis case is missing or unauthorized")
        job_id = uuid4()
        await execute_returning(
            self.session,
            """
            INSERT INTO integration.background_job (
                id, job_type, resource_type, resource_id, status,
                progress_percent, current_step, correlation_id, requested_by,
                priority, attempt_count, max_attempts, scheduled_at,
                created_at, updated_at, version
            ) VALUES (
                :job_id, 'REPORT_GENERATION', 'REPORT', :report_id, 'QUEUED',
                0, 'AWAITING_PUBLICATION', :correlation_id, :actor_id,
                5, 0, 5, :now, :now, :now, 1
            ) RETURNING id
            """,
            {
                "job_id": job_id,
                "report_id": report_id,
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
                :outbox_id, 'REPORT', :report_id,
                'report.generation.requested', 1, CAST(:report_id AS text),
                CAST(:event AS jsonb), CAST(:headers AS jsonb),
                'PENDING', 0, :now, :now
            ) RETURNING id
            """,
            {
                "outbox_id": outbox_id,
                "report_id": report_id,
                "event": event,
                "headers": headers,
                "now": now,
            },
        )
        row["job_id"] = job_id
        row["outbox_id"] = outbox_id
        return row

    async def create_claim(self, values: Mapping[str, Any]) -> Record:
        require_fields(
            values,
            (
                "id",
                "report_id",
                "section",
                "claim_text",
                "claim_type",
                "validation_status",
                "created_at",
            ),
        )
        row = await execute_returning(
            self.session,
            insert_sql("ai.report_claim", values, _CLAIM_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Report claim insert returned no row")
        return row

    async def link_claim_evidence(
        self,
        claim_id: UUID,
        evidence_link_id: UUID,
        support_type: str,
    ) -> Record | None:
        return await execute_returning(
            self.session,
            """
            INSERT INTO ai.report_claim_evidence (
                claim_id, evidence_link_id, support_type
            ) VALUES (:claim_id, :evidence_link_id, :support_type)
            ON CONFLICT (claim_id, evidence_link_id)
            DO UPDATE SET support_type = EXCLUDED.support_type
            RETURNING *
            """,
            {
                "claim_id": claim_id,
                "evidence_link_id": evidence_link_id,
                "support_type": support_type,
            },
        )

    async def get(self, report_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT r.*, om.bucket_name, om.object_key, om.object_version_id,
                   om.mime_type AS pdf_mime_type, om.size_bytes AS pdf_size_bytes
            FROM ai.report AS r
            JOIN ai.analysis_case AS ac ON ac.id = r.analysis_case_id
            LEFT JOIN storage.object_metadata AS om ON om.id = r.pdf_object_id
            WHERE r.id = :report_id
            """,
            {"report_id": report_id},
        )

    async def claims(self, report_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT rc.* FROM ai.report AS r
            JOIN ai.analysis_case AS ac ON ac.id = r.analysis_case_id
            JOIN ai.report_claim AS rc ON rc.report_id = r.id
            WHERE r.id = :report_id
            ORDER BY rc.section, rc.created_at, rc.id
            """,
            {"report_id": report_id},
        )

    async def review(
        self,
        report_id: UUID,
        reviewer_id: UUID,
        status: str,
        review_note: str | None = None,
    ) -> Record | None:
        if status not in {"REVIEWED", "CHANGES_REQUESTED", "APPROVED"}:
            raise ValueError("Invalid report review status")
        return await execute_returning(
            self.session,
            """
            UPDATE ai.report
            SET status = :status,
                reviewed_by = :reviewer_id,
                approved_by = CASE WHEN :status = 'APPROVED' THEN :reviewer_id ELSE approved_by END,
                json_payload = jsonb_set(
                    json_payload, '{review}',
                    jsonb_build_object(
                        'status', :status,
                        'reviewer_id', CAST(:reviewer_id AS text),
                        'note', :review_note,
                        'reviewed_at', to_jsonb(CURRENT_TIMESTAMP)
                    ), true
                )
            WHERE id = :report_id
            RETURNING *
            """,
            {
                "report_id": report_id,
                "reviewer_id": reviewer_id,
                "status": status,
                "review_note": review_note,
            },
        )
