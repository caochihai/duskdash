"""Request idempotency independent of HTTP and persistence implementations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.services.protocols import IdempotencyRepositoryLike


class IdempotencyConflictError(ValueError):
    """Raised when an existing key is reused for a different request body."""


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status_code: int
    payload: Mapping[str, Any]
    resource_type: str | None = None
    resource_id: UUID | None = None


def canonical_request_hash(payload: Mapping[str, Any] | list[Any] | None) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class IdempotencyService:
    def __init__(self, repository: IdempotencyRepositoryLike) -> None:
        self._repository = repository

    async def replay(
        self,
        *,
        actor_id: UUID,
        operation_name: str,
        idempotency_key: UUID,
        request_payload: Mapping[str, Any] | list[Any] | None,
    ) -> StoredResponse | None:
        row = await self._repository.get(
            actor_id=actor_id,
            operation_name=operation_name,
            idempotency_key=idempotency_key,
        )
        if row is None:
            return None
        current_hash = canonical_request_hash(request_payload)
        if str(row["request_hash"]) != current_hash:
            raise IdempotencyConflictError("Idempotency-Key was already used with a different request")
        resource_id = row.get("resource_id")
        return StoredResponse(
            status_code=int(row.get("response_status") or 200),
            payload=row.get("response_payload") or {},
            resource_type=row.get("resource_type"),
            resource_id=UUID(str(resource_id)) if resource_id else None,
        )

    async def remember(
        self,
        *,
        actor_id: UUID,
        operation_name: str,
        idempotency_key: UUID,
        request_payload: Mapping[str, Any] | list[Any] | None,
        response: StoredResponse,
    ) -> None:
        await self._repository.create(
            actor_id=actor_id,
            operation_name=operation_name,
            idempotency_key=idempotency_key,
            request_hash=canonical_request_hash(request_payload),
            response_status=response.status_code,
            response_payload=response.payload,
            resource_type=response.resource_type,
            resource_id=response.resource_id,
        )

