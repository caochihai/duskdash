"""Append-only, tamper-evident audit event persistence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from app.compat import UTC
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_all, fetch_one, pagination, require_fields

_AUDIT_FIELDS = (
    "id",
    "event_time",
    "actor_type",
    "actor_id",
    "action",
    "resource_type",
    "resource_id",
    "customer_id",
    "loan_application_id",
    "result",
    "ip_address",
    "user_agent",
    "session_id",
    "request_id",
    "correlation_id",
    "metadata",
    "created_at",
)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(
        self,
        values: Mapping[str, Any] | None = None,
        *,
        actor_type: str | None = None,
        actor_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        result: str | None = None,
        request_id: UUID | None = None,
        correlation_id: UUID | None = None,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Record:
        if values is None:
            now = datetime.now(UTC)
            values = {
                "id": uuid4(),
                "event_time": now,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "customer_id": customer_id,
                "loan_application_id": loan_application_id,
                "result": result,
                "ip_address": None,
                "user_agent": None,
                "session_id": None,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "metadata": dict(metadata or {}),
                "created_at": now,
            }
        require_fields(
            values,
            ("id", "event_time", "actor_type", "action", "resource_type", "result", "created_at"),
        )
        if any(values.get(field) is None for field in ("actor_type", "action", "resource_type", "result")):
            raise ValueError("actor_type, action, resource_type and result are required")
        unknown = set(values) - set(_AUDIT_FIELDS)
        if unknown:
            raise ValueError(f"Unsupported audit fields: {', '.join(sorted(unknown))}")

        # A transaction-level global lock makes the previous_hash chain linear.
        await self.session.execute(text("SELECT pg_advisory_xact_lock(1935765471)"))
        previous = await fetch_one(
            self.session,
            """
            SELECT event_hash FROM audit.audit_event
            ORDER BY event_time DESC, created_at DESC, id DESC
            LIMIT 1
            FOR UPDATE
            """,
        )
        previous_hash = str(previous["event_hash"]) if previous else None
        payload = {field: values.get(field) for field in _AUDIT_FIELDS}
        payload["metadata"] = dict(values.get("metadata") or {})
        canonical = json.dumps(
            _canonical_value(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        event_hash = sha256(f"{previous_hash or ''}\n{canonical}".encode()).hexdigest()
        params = {**payload, "previous_hash": previous_hash, "event_hash": event_hash}
        row = await execute_returning(
            self.session,
            """
            INSERT INTO audit.audit_event (
                id, event_time, actor_type, actor_id, action, resource_type,
                resource_id, customer_id, loan_application_id, result,
                ip_address, user_agent, session_id, request_id, correlation_id,
                metadata, previous_hash, event_hash, created_at
            ) VALUES (
                :id, :event_time, :actor_type, :actor_id, :action, :resource_type,
                :resource_id, :customer_id, :loan_application_id, :result,
                CAST(:ip_address AS inet), :user_agent, :session_id, :request_id,
                :correlation_id, CAST(:metadata AS jsonb), :previous_hash,
                :event_hash, :created_at
            )
            RETURNING *
            """,
            params,
        )
        if row is None:
            raise RuntimeError("Audit insert returned no row")
        return row

    async def list(
        self,
        page: int = 1,
        page_size: int = 50,
        actor_id: UUID | None = None,
        action: str | None = None,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
    ) -> list[Record]:
        limit, offset = pagination(page, page_size)
        return await fetch_all(
            self.session,
            """
            SELECT ae.*, count(*) OVER () AS total_count
            FROM audit.audit_event AS ae
            WHERE (CAST(:actor_id AS UUID) IS NULL OR ae.actor_id = CAST(:actor_id AS UUID))
              AND (CAST(:action AS TEXT) IS NULL OR ae.action = CAST(:action AS TEXT))
              AND (CAST(:customer_id AS UUID) IS NULL
                   OR ae.customer_id = CAST(:customer_id AS UUID))
              AND (CAST(:loan_id AS UUID) IS NULL
                   OR ae.loan_application_id = CAST(:loan_id AS UUID))
            ORDER BY ae.event_time DESC, ae.id DESC
            LIMIT :limit OFFSET :offset
            """,
            {
                "actor_id": actor_id,
                "action": action,
                "customer_id": customer_id,
                "loan_id": loan_application_id,
                "limit": limit,
                "offset": offset,
            },
        )
