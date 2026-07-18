"""Atomic HTTP idempotency execution inside the request database transaction."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta
from app.compat import UTC
from typing import Any
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError
from app.repositories.idempotency_repository import IdempotencyRepository
from app.services.idempotency_service import canonical_request_hash


async def execute_idempotent(
    *,
    session: AsyncSession,
    actor_id: UUID,
    operation_name: str,
    idempotency_key: UUID,
    request_payload: Mapping[str, Any] | list[Any] | None,
    response_status: int,
    resource_type: str,
    operation: Callable[[], Awaitable[Mapping[str, Any]]],
) -> Mapping[str, Any]:
    """Claim the key, run once, and cache the result in the same transaction."""

    repository = IdempotencyRepository(session)
    request_hash = canonical_request_hash(request_payload)
    now = datetime.now(UTC)
    record = await repository.begin(
        uuid4(),
        idempotency_key,
        actor_id,
        operation_name,
        request_hash,
        now + timedelta(hours=24),
        now,
    )
    state = str(record.get("_state", ""))
    if state == "CONFLICT":
        raise ConflictError(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency-Key was already used with a different request.",
        )
    if state == "IN_PROGRESS":
        raise ConflictError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "A request with this Idempotency-Key is still in progress.",
        )
    if state == "REPLAY":
        payload = record.get("response_payload")
        return dict(payload) if isinstance(payload, Mapping) else {}
    if state != "OWNER":
        raise RuntimeError("Invalid idempotency record state")

    result = await operation()
    payload = jsonable_encoder(dict(result))
    resource_value = result.get("id")
    resource_id = UUID(str(resource_value)) if resource_value else None
    completed = await repository.complete(
        UUID(str(record["id"])),
        request_hash,
        response_status,
        payload,
        resource_type,
        resource_id,
    )
    if completed is None:
        raise RuntimeError("Idempotency response could not be stored")
    return result
