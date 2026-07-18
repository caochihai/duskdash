"""Employee notification persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_all, pagination, rows_with_total


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        employee_id: UUID,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> tuple[list[Record], int]:
        limit, offset = pagination(page, page_size)
        rows = await fetch_all(
            self.session,
            """
            SELECT n.*, count(*) OVER () AS total_count
            FROM integration.notification AS n
            WHERE n.employee_id = :employee_id
              AND (CAST(:status AS TEXT) IS NULL
                   OR n.status = CAST(:status AS TEXT))
            ORDER BY n.created_at DESC, n.id
            LIMIT :limit OFFSET :offset
            """,
            {"employee_id": employee_id, "status": status, "limit": limit, "offset": offset},
        )
        return rows_with_total(rows)

    async def mark_read(self, notification_id: UUID, employee_id: UUID) -> Record | None:
        return await execute_returning(
            self.session,
            """
            UPDATE integration.notification
            SET status = 'READ', read_at = CURRENT_TIMESTAMP
            WHERE id = :notification_id AND employee_id = :employee_id
              AND status = 'UNREAD'
            RETURNING *
            """,
            {"notification_id": notification_id, "employee_id": employee_id},
        )
