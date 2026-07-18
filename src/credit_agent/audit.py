"""Small audit adapters; production systems should provide an append-only sink."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .models import AuditEvent


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()


class NullAuditSink:
    durable = False

    async def emit(self, event: AuditEvent) -> None:
        del event


class InMemoryAuditSink:
    """Useful for tests and demos; it is not a durable production audit log."""

    durable = False

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> None:
        self.events.append(event.model_copy(deep=True))
