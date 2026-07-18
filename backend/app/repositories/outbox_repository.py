"""Transactional outbox persistence and concurrent publisher claiming."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_all, insert_sql, require_fields

_OUTBOX_COLUMNS = frozenset(
    {
        "id",
        "aggregate_type",
        "aggregate_id",
        "event_type",
        "event_version",
        "partition_key",
        "payload",
        "headers",
        "status",
        "attempt_count",
        "available_at",
        "locked_at",
        "locked_by",
        "published_at",
        "last_error",
        "created_at",
    }
)


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, values: Mapping[str, Any]) -> Record:
        require_fields(
            values,
            (
                "id",
                "aggregate_type",
                "aggregate_id",
                "event_type",
                "event_version",
                "partition_key",
                "payload",
                "available_at",
                "created_at",
            ),
        )
        payload = dict(values)
        payload.setdefault("headers", {})
        payload.setdefault("status", "PENDING")
        payload.setdefault("attempt_count", 0)
        row = await execute_returning(
            self.session,
            insert_sql("integration.event_outbox", payload, _OUTBOX_COLUMNS),
            payload,
        )
        if row is None:
            raise RuntimeError("Outbox insert returned no row")
        return row

    async def claim(
        self,
        publisher_id: str,
        batch_size: int = 50,
        now: datetime | None = None,
        stale_after_seconds: int = 300,
    ) -> list[Record]:
        if not publisher_id.strip():
            raise ValueError("publisher_id is required")
        if not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be between 1 and 500")
        if stale_after_seconds < 1:
            raise ValueError("stale_after_seconds must be positive")
        return await fetch_all(
            self.session,
            """
            WITH candidates AS (
                SELECT id
                FROM integration.event_outbox
                WHERE (
                    status = 'PENDING' AND available_at <= COALESCE(:now, CURRENT_TIMESTAMP)
                ) OR (
                    status = 'PROCESSING'
                    AND locked_at < COALESCE(:now, CURRENT_TIMESTAMP)
                                    - make_interval(secs => :stale_after_seconds)
                )
                ORDER BY available_at, created_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT :batch_size
            )
            UPDATE integration.event_outbox AS eo
            SET status = 'PROCESSING',
                locked_at = COALESCE(:now, CURRENT_TIMESTAMP),
                locked_by = :publisher_id
            FROM candidates
            WHERE eo.id = candidates.id
            RETURNING eo.*
            """,
            {
                "publisher_id": publisher_id,
                "batch_size": batch_size,
                "now": now,
                "stale_after_seconds": stale_after_seconds,
            },
        )

    async def claim_pending_for_producer(
        self,
        producer: str,
        batch_size: int,
        locked_by: str | None = None,
        *,
        publisher_id: str | None = None,
        stale_after_seconds: int = 300,
    ) -> list[Record]:
        """Claim only envelopes owned by one least-privilege Kafka principal."""
        owner = publisher_id or locked_by
        if not producer.strip() or owner is None or not owner.strip():
            raise ValueError("producer and locked_by are required")
        if not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be between 1 and 500")
        return await fetch_all(
            self.session,
            """
            WITH candidates AS (
                SELECT id
                FROM integration.event_outbox
                WHERE payload ->> 'producer' = :producer
                  AND (
                      (status = 'PENDING' AND available_at <= CURRENT_TIMESTAMP)
                      OR (
                          status = 'PROCESSING'
                          AND locked_at < CURRENT_TIMESTAMP
                                          - make_interval(secs => :stale_after_seconds)
                      )
                  )
                ORDER BY available_at, created_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT :batch_size
            )
            UPDATE integration.event_outbox AS eo
            SET status = 'PROCESSING', locked_at = CURRENT_TIMESTAMP,
                locked_by = :locked_by
            FROM candidates
            WHERE eo.id = candidates.id
            RETURNING eo.*
            """,
            {
                "producer": producer,
                "batch_size": batch_size,
                "locked_by": owner,
                "stale_after_seconds": stale_after_seconds,
            },
        )

    async def retry(
        self,
        event_id: UUID,
        available_at: datetime,
    ) -> Record | None:
        """Explicitly requeue a terminal failed event after operator review."""
        return await execute_returning(
            self.session,
            """
            UPDATE integration.event_outbox
            SET status = 'PENDING', available_at = :available_at,
                locked_at = NULL, locked_by = NULL, last_error = NULL
            WHERE id = :event_id AND status = 'FAILED'
            RETURNING *
            """,
            {"event_id": event_id, "available_at": available_at},
        )

    async def mark_published(
        self,
        event_id: UUID,
        publisher_id: str,
        published_at: datetime | None = None,
    ) -> Record | None:
        return await execute_returning(
            self.session,
            """
            UPDATE integration.event_outbox
            SET status = 'PUBLISHED', published_at = COALESCE(:published_at, CURRENT_TIMESTAMP),
                locked_at = NULL, locked_by = NULL, last_error = NULL
            WHERE id = :event_id AND status = 'PROCESSING' AND locked_by = :locked_by
            RETURNING *
            """,
            {"event_id": event_id, "locked_by": publisher_id, "published_at": published_at},
        )

    async def mark_failed(
        self,
        event_id: UUID,
        publisher_id: str,
        error_message_safe: str,
        backoff_seconds: int,
        max_attempts: int = 10,
    ) -> Record | None:
        if backoff_seconds < 0 or max_attempts < 1:
            raise ValueError("Invalid outbox retry configuration")
        safe_error = error_message_safe[:2000]
        return await execute_returning(
            self.session,
            """
            UPDATE integration.event_outbox
            SET attempt_count = attempt_count + 1,
                status = CASE WHEN attempt_count + 1 >= :max_attempts
                              THEN 'FAILED' ELSE 'PENDING' END,
                available_at = CURRENT_TIMESTAMP + make_interval(secs => :backoff_seconds),
                locked_at = NULL, locked_by = NULL,
                last_error = :last_error
            WHERE id = :event_id AND status = 'PROCESSING' AND locked_by = :locked_by
            RETURNING *
            """,
            {
                "event_id": event_id,
                "locked_by": publisher_id,
                "max_attempts": max_attempts,
                "backoff_seconds": backoff_seconds,
                "last_error": safe_error,
            },
        )
