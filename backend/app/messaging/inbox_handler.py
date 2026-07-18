"""Repository protocol and duplicate-safe Kafka Inbox handler."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.messaging.event_envelope import EventEnvelope


class InboxRepository(Protocol):
    """Persistence contract over ``integration.event_inbox``.

    ``try_start`` must atomically insert/claim UNIQUE(event_id, consumer_name)
    and return False for an already completed event.
    """

    async def try_start(self, event_id: UUID, *, consumer_name: str, event_type: str) -> bool: ...

    async def mark_completed(
        self, event_id: UUID, *, consumer_name: str, result_reference_id: UUID | None = None
    ) -> None: ...

    async def mark_failed(
        self, event_id: UUID, *, consumer_name: str, error_code: str
    ) -> None: ...


class InboxHandler:
    """Run a business callback once; callers commit Kafka only afterwards."""

    def __init__(self, repository: InboxRepository, *, consumer_name: str) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,99}", consumer_name):
            raise ValueError("consumer_name must be a stable lowercase service name")
        self._repository = repository
        self.consumer_name = consumer_name

    async def handle(
        self,
        event: EventEnvelope,
        callback: Callable[[EventEnvelope], Awaitable[UUID | None]],
    ) -> bool:
        claimed = await self._repository.try_start(
            event.event_id, consumer_name=self.consumer_name, event_type=event.event_type
        )
        if not claimed:
            return False
        try:
            result_id = await callback(event)
        except Exception as exc:
            await self._repository.mark_failed(
                event.event_id,
                consumer_name=self.consumer_name,
                error_code=_error_code(exc),
            )
            raise
        await self._repository.mark_completed(
            event.event_id,
            consumer_name=self.consumer_name,
            result_reference_id=result_id,
        )
        return True


class SqlInboxRepository(Protocol):
    """Shape of the concrete SQL repository owned by the persistence layer."""

    async def begin(
        self,
        inbox_id: UUID,
        event_id: UUID,
        consumer_name: str,
        event_type: str,
        received_at: datetime,
        created_at: datetime,
    ) -> Mapping[str, Any] | None: ...

    async def complete(
        self, event_id: UUID, consumer_name: str, result_reference_id: UUID | None = None
    ) -> Mapping[str, Any] | None: ...

    async def fail(
        self, event_id: UUID, consumer_name: str, error_code: str
    ) -> Mapping[str, Any] | None: ...


class InboxRepositoryAdapter:
    """Adapt the SQL repository without importing its concrete implementation."""

    def __init__(self, repository: SqlInboxRepository) -> None:
        self._repository = repository

    async def try_start(self, event_id: UUID, *, consumer_name: str, event_type: str) -> bool:
        now = datetime.now(UTC)
        row = await self._repository.begin(
            uuid4(), event_id, consumer_name, event_type, now, now
        )
        return row is not None

    async def mark_completed(
        self, event_id: UUID, *, consumer_name: str, result_reference_id: UUID | None = None
    ) -> None:
        await self._repository.complete(event_id, consumer_name, result_reference_id)

    async def mark_failed(
        self, event_id: UUID, *, consumer_name: str, error_code: str
    ) -> None:
        await self._repository.fail(event_id, consumer_name, error_code)


def _error_code(exc: Exception) -> str:
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", type(exc).__name__).upper()
    return name[:50]
