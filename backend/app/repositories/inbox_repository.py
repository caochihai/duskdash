"""Consumer inbox deduplication state machine."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_one


class InboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def begin(
        self,
        inbox_id: UUID,
        event_id: UUID,
        consumer_name: str,
        event_type: str,
        received_at: datetime,
        created_at: datetime,
    ) -> Record | None:
        """Claim a new or failed delivery; completed/in-flight duplicates return None."""
        return await execute_returning(
            self.session,
            """
            INSERT INTO integration.event_inbox (
                id, event_id, consumer_name, event_type, received_at,
                processed_at, status, result_reference_id, error_code, created_at
            ) VALUES (
                :id, :event_id, :consumer_name, :event_type, :received_at,
                NULL, 'PROCESSING', NULL, NULL, :created_at
            )
            ON CONFLICT (event_id, consumer_name) DO UPDATE
            SET status = 'PROCESSING', received_at = EXCLUDED.received_at,
                processed_at = NULL, error_code = NULL
            WHERE event_inbox.status = 'FAILED'
            RETURNING *
            """,
            {
                "id": inbox_id,
                "event_id": event_id,
                "consumer_name": consumer_name,
                "event_type": event_type,
                "received_at": received_at,
                "created_at": created_at,
            },
        )

    async def complete(
        self,
        event_id: UUID,
        consumer_name: str,
        result_reference_id: UUID | None = None,
    ) -> Record | None:
        return await execute_returning(
            self.session,
            """
            UPDATE integration.event_inbox
            SET status = 'COMPLETED', processed_at = CURRENT_TIMESTAMP,
                result_reference_id = :result_reference_id, error_code = NULL
            WHERE event_id = :event_id AND consumer_name = :consumer_name
              AND status = 'PROCESSING'
            RETURNING *
            """,
            {
                "event_id": event_id,
                "consumer_name": consumer_name,
                "result_reference_id": result_reference_id,
            },
        )

    async def fail(
        self,
        event_id: UUID,
        consumer_name: str,
        error_code: str,
    ) -> Record | None:
        return await execute_returning(
            self.session,
            """
            UPDATE integration.event_inbox
            SET status = 'FAILED', processed_at = CURRENT_TIMESTAMP,
                error_code = :error_code
            WHERE event_id = :event_id AND consumer_name = :consumer_name
              AND status = 'PROCESSING'
            RETURNING *
            """,
            {
                "event_id": event_id,
                "consumer_name": consumer_name,
                "error_code": error_code[:50],
            },
        )

    async def is_processed(self, event_id: UUID, consumer_name: str) -> bool:
        row = await fetch_one(
            self.session,
            """
            SELECT status = 'COMPLETED' AS processed
            FROM integration.event_inbox
            WHERE event_id = :event_id AND consumer_name = :consumer_name
            """,
            {"event_id": event_id, "consumer_name": consumer_name},
        )
        return bool(row and row["processed"])

