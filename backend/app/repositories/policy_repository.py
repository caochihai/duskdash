"""Approved policy and effective-date retrieval."""

from __future__ import annotations

import builtins
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, fetch_all, fetch_one, pagination


class PolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str = "ACTIVE",
        *,
        as_of: date | None = None,
    ) -> builtins.list[Record]:
        if as_of is not None:
            return await fetch_all(
                self.session,
                """
                SELECT p.*, pv.id AS policy_version_id, pv.version_number,
                       pv.effective_from, pv.effective_until,
                       pv.source_document_id, pv.approved_by, pv.approved_at
                FROM policy.policy AS p
                JOIN LATERAL (
                    SELECT candidate.* FROM policy.policy_version AS candidate
                    WHERE candidate.policy_id = p.id
                      AND candidate.status = 'ACTIVE'
                      AND candidate.effective_from <= :as_of
                      AND (candidate.effective_until IS NULL
                           OR candidate.effective_until >= :as_of)
                    ORDER BY candidate.effective_from DESC,
                             candidate.created_at DESC, candidate.id
                    LIMIT 1
                ) AS pv ON TRUE
                WHERE p.status = 'ACTIVE'
                ORDER BY p.policy_code, p.id
                """,
                {"as_of": as_of},
            )
        limit, offset = pagination(page, page_size)
        return await fetch_all(
            self.session,
            """
            SELECT p.*, count(*) OVER () AS total_count
            FROM policy.policy AS p
            WHERE (CAST(:status AS TEXT) IS NULL
                   OR p.status = CAST(:status AS TEXT))
            ORDER BY p.policy_code, p.id
            LIMIT :limit OFFSET :offset
            """,
            {"status": status, "limit": limit, "offset": offset},
        )

    async def search(
        self,
        query: str,
        effective_on: date | None = None,
        limit: int = 20,
        *,
        as_of: date | None = None,
    ) -> builtins.list[Record]:
        if not query.strip():
            return []
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        target_date = as_of or effective_on
        if target_date is None:
            raise ValueError("as_of is required")
        return await fetch_all(
            self.session,
            """
            SELECT pc.id AS clause_id, pc.policy_version_id,
                   pc.clause_number, pc.title, pc.content, pc.page_number,
                   pc.metadata, pv.version_number, pv.effective_from,
                   pv.effective_until, p.id AS policy_id, p.policy_code,
                   p.policy_name, p.policy_type
            FROM policy.policy_clause AS pc
            JOIN policy.policy_version AS pv ON pv.id = pc.policy_version_id
            JOIN policy.policy AS p ON p.id = pv.policy_id
            WHERE p.status = 'ACTIVE' AND pv.status = 'ACTIVE'
              AND pv.effective_from <= :effective_on
              AND (pv.effective_until IS NULL OR pv.effective_until >= :effective_on)
              AND (pc.content ILIKE :pattern OR pc.title ILIKE :pattern
                   OR pc.clause_number ILIKE :pattern)
            ORDER BY pv.effective_from DESC, p.policy_code, pc.clause_number
            LIMIT :limit
            """,
            {"effective_on": target_date, "pattern": f"%{query.strip()}%", "limit": limit},
        )

    async def get_clause(
        self,
        clause_id: UUID,
        effective_on: date | None = None,
        *,
        as_of: date | None = None,
    ) -> Record | None:
        target_date = as_of or effective_on
        return await fetch_one(
            self.session,
            """
            SELECT pc.*, pv.policy_id, pv.version_number, pv.effective_from,
                   pv.effective_until, pv.status AS version_status,
                   p.policy_code, p.policy_name, p.policy_type
            FROM policy.policy_clause AS pc
            JOIN policy.policy_version AS pv ON pv.id = pc.policy_version_id
            JOIN policy.policy AS p ON p.id = pv.policy_id
            WHERE pc.id = :clause_id
              AND (CAST(:effective_on AS DATE) IS NULL OR (
                  pv.effective_from <= CAST(:effective_on AS DATE)
                  AND (pv.effective_until IS NULL
                       OR pv.effective_until >= CAST(:effective_on AS DATE))
              ))
            """,
            {"clause_id": clause_id, "effective_on": target_date},
        )

    async def effective_version(self, policy_id: UUID, effective_on: date) -> Record | None:
        """Select the latest approved active version valid on the exact date."""
        return await fetch_one(
            self.session,
            """
            SELECT pv.* FROM policy.policy_version AS pv
            JOIN policy.policy AS p ON p.id = pv.policy_id
            WHERE pv.policy_id = :policy_id
              AND p.status = 'ACTIVE' AND pv.status = 'ACTIVE'
              AND pv.effective_from <= :effective_on
              AND (pv.effective_until IS NULL OR pv.effective_until >= :effective_on)
            ORDER BY pv.effective_from DESC, pv.created_at DESC, pv.id
            LIMIT 1
            """,
            {"policy_id": policy_id, "effective_on": effective_on},
        )
