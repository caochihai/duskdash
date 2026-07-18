"""Finding and evidence retrieval with case/customer RLS ancestry."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, fetch_all, fetch_one


class EvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_finding(self, finding_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT f.* FROM ai.finding AS f
            JOIN ai.analysis_case AS ac ON ac.id = f.analysis_case_id
            WHERE f.id = :finding_id
            """,
            {"finding_id": finding_id},
        )

    async def get_evidence(self, finding_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT el.* FROM ai.finding AS f
            JOIN ai.analysis_case AS ac ON ac.id = f.analysis_case_id
            JOIN ai.evidence_link AS el ON el.finding_id = f.id
            WHERE f.id = :finding_id
            ORDER BY el.evidence_role, el.created_at, el.id
            """,
            {"finding_id": finding_id},
        )

