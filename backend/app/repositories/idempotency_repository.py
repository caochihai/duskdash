"""Actor/operation-scoped HTTP idempotency records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from app.compat import UTC
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_one


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def begin(
        self,
        record_id: UUID,
        idempotency_key: UUID,
        actor_id: UUID,
        operation_name: str,
        request_hash: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> Record:
        inserted = await execute_returning(
            self.session,
            """
            INSERT INTO integration.idempotency_record (
                id, idempotency_key, actor_id, operation_name, request_hash,
                response_status, response_payload, resource_type, resource_id,
                expires_at, created_at
            ) VALUES (
                :id, :key, :actor_id, :operation, :request_hash,
                NULL, NULL, NULL, NULL, :expires_at, :created_at
            )
            ON CONFLICT (actor_id, operation_name, idempotency_key) DO UPDATE
            SET id = EXCLUDED.id, request_hash = EXCLUDED.request_hash,
                response_status = NULL, response_payload = NULL,
                resource_type = NULL, resource_id = NULL,
                expires_at = EXCLUDED.expires_at, created_at = EXCLUDED.created_at
            WHERE idempotency_record.expires_at <= CURRENT_TIMESTAMP
            RETURNING *
            """,
            {
                "id": record_id,
                "key": idempotency_key,
                "actor_id": actor_id,
                "operation": operation_name,
                "request_hash": request_hash,
                "expires_at": expires_at,
                "created_at": created_at,
            },
        )
        if inserted is not None:
            inserted["_state"] = "OWNER"
            return inserted

        existing = await self.get(idempotency_key, actor_id, operation_name)
        if existing is None:
            raise RuntimeError("Idempotency conflict row disappeared")
        if existing["request_hash"] != request_hash:
            existing["_state"] = "CONFLICT"
        elif existing["response_status"] is not None:
            existing["_state"] = "REPLAY"
        else:
            existing["_state"] = "IN_PROGRESS"
        return existing

    async def create(
        self,
        *,
        actor_id: UUID,
        operation_name: str,
        idempotency_key: UUID,
        request_hash: str,
        response_status: int,
        response_payload: Mapping[str, Any],
        resource_type: str | None,
        resource_id: UUID | None,
    ) -> Record:
        now = datetime.now(UTC)
        row = await execute_returning(
            self.session,
            """
            INSERT INTO integration.idempotency_record (
                id, idempotency_key, actor_id, operation_name, request_hash,
                response_status, response_payload, resource_type, resource_id,
                expires_at, created_at
            ) VALUES (
                :id, :key, :actor_id, :operation, :request_hash,
                :response_status, CAST(:response_payload AS jsonb),
                :resource_type, :resource_id, :expires_at, :created_at
            )
            ON CONFLICT (actor_id, operation_name, idempotency_key) DO UPDATE
            SET response_status = EXCLUDED.response_status,
                response_payload = EXCLUDED.response_payload,
                resource_type = EXCLUDED.resource_type,
                resource_id = EXCLUDED.resource_id,
                expires_at = EXCLUDED.expires_at
            WHERE idempotency_record.request_hash = EXCLUDED.request_hash
            RETURNING *
            """,
            {
                "id": uuid4(),
                "key": idempotency_key,
                "actor_id": actor_id,
                "operation": operation_name,
                "request_hash": request_hash,
                "response_status": response_status,
                "response_payload": dict(response_payload),
                "resource_type": resource_type,
                "resource_id": resource_id,
                "expires_at": now + timedelta(hours=24),
                "created_at": now,
            },
        )
        if row is None:
            raise ValueError("Idempotency key conflicts with a different request")
        return row

    async def get(
        self,
        idempotency_key: UUID,
        actor_id: UUID,
        operation_name: str,
    ) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT * FROM integration.idempotency_record
            WHERE idempotency_key = :key AND actor_id = :actor_id
              AND operation_name = :operation
            """,
            {"key": idempotency_key, "actor_id": actor_id, "operation": operation_name},
        )

    async def complete(
        self,
        record_id: UUID,
        request_hash: str,
        response_status: int,
        response_payload: dict[str, object],
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> Record | None:
        return await execute_returning(
            self.session,
            """
            UPDATE integration.idempotency_record
            SET response_status = :response_status,
                response_payload = CAST(:response_payload AS jsonb),
                resource_type = :resource_type, resource_id = :resource_id
            WHERE id = :record_id AND request_hash = :request_hash
              AND response_status IS NULL
            RETURNING *
            """,
            {
                "record_id": record_id,
                "request_hash": request_hash,
                "response_status": response_status,
                "response_payload": response_payload,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )
