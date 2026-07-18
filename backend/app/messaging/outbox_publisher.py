"""Repository-agnostic, principal-scoped PostgreSQL Outbox publisher."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from app.messaging.event_envelope import EventEnvelope


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    """Projection of ``integration.event_outbox`` required for publishing."""

    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    event_version: int
    partition_key: str
    payload: Mapping[str, Any]
    headers: Mapping[str, Any]
    attempt_count: int
    created_at: datetime

    @property
    def producer(self) -> str:
        value = self.payload.get("producer")
        if not isinstance(value, str) or not value:
            raise ValueError("outbox payload.producer is required for ACL-safe routing")
        return value

    @property
    def topic(self) -> str:
        value = self.headers.get("topic")
        if not isinstance(value, str) or not value:
            raise ValueError("outbox headers.topic is required for explicit routing")
        return value

    def to_envelope(self) -> EventEnvelope:
        """Build the exact envelope; no sensitive data is synthesized here."""

        envelope = EventEnvelope.model_validate(self.payload)
        if envelope.event_id != self.id:
            raise ValueError("outbox row id and envelope event_id differ")
        if envelope.event_type != self.event_type or envelope.event_version != self.event_version:
            raise ValueError("outbox event columns and envelope differ")
        if str(envelope.partition_key) != self.partition_key:
            raise ValueError("outbox partition_key and envelope differ")
        if envelope.resource.id != self.aggregate_id or envelope.resource.type != self.aggregate_type:
            raise ValueError("outbox aggregate columns and envelope resource differ")
        return envelope

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> OutboxRecord:
        return cls(
            id=UUID(str(value["id"])),
            aggregate_type=str(value["aggregate_type"]),
            aggregate_id=UUID(str(value["aggregate_id"])),
            event_type=str(value["event_type"]),
            event_version=int(value["event_version"]),
            partition_key=str(value["partition_key"]),
            payload=value["payload"],
            headers=value.get("headers", {}),
            attempt_count=int(value.get("attempt_count", 0)),
            created_at=value["created_at"],
        )


class OutboxRepository(Protocol):
    """Implemented by the SQL repository with FOR UPDATE SKIP LOCKED."""

    async def claim_pending_for_producer(
        self, *, producer: str, publisher_id: str, batch_size: int
    ) -> Sequence[OutboxRecord | Mapping[str, Any]]: ...

    async def mark_published(
        self, event_id: UUID, publisher_id: str, published_at: datetime | None = None
    ) -> object: ...

    async def mark_failed(
        self,
        event_id: UUID,
        publisher_id: str,
        error_message_safe: str,
        backoff_seconds: int,
        max_attempts: int = 10,
    ) -> object: ...


class EnvelopeProducer(Protocol):
    principal: str

    async def send_envelope(self, envelope: EventEnvelope, *, topic: str | None = None) -> object: ...


class OutboxPublisher:
    """Publish only rows created for this process's exact SCRAM principal.

    Run one instance per origin identity. This prevents a bank-api publisher
    from claiming worker events that its Kafka ACL cannot write, without ever
    resorting to the kafka-admin account.
    """

    def __init__(
        self,
        repository: OutboxRepository,
        producer: EnvelopeProducer,
        *,
        publisher_id: str,
        batch_size: int = 100,
        poll_interval_seconds: float = 1.0,
        max_attempts: int = 8,
        retry_base_seconds: float = 1.0,
        retry_max_seconds: float = 300.0,
    ) -> None:
        if not 1 <= batch_size <= 100:
            raise ValueError("outbox batch_size must be between 1 and 100")
        if producer.principal == "kafka-admin":
            raise ValueError("Kafka admin credentials are forbidden for Outbox publishing")
        self._repository = repository
        self._producer = producer
        self._publisher_id = publisher_id
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds
        self._max_attempts = max_attempts
        self._retry_base = retry_base_seconds
        self._retry_max = retry_max_seconds

    async def run_once(self) -> int:
        records = await self._repository.claim_pending_for_producer(
            producer=self._producer.principal,
            publisher_id=self._publisher_id,
            batch_size=self._batch_size,
        )
        published = 0
        for claimed in records:
            record = claimed if isinstance(claimed, OutboxRecord) else OutboxRecord.from_mapping(claimed)
            if record.producer != self._producer.principal:
                raise RuntimeError("repository returned an outbox row for another Kafka principal")
            try:
                await self._producer.send_envelope(record.to_envelope(), topic=record.topic)
            except Exception as exc:  # publisher must persist and continue per row
                attempts = record.attempt_count + 1
                safe_error = _safe_error(exc)
                delay = int(min(self._retry_max, self._retry_base * (2 ** (attempts - 1))))
                await self._repository.mark_failed(
                    record.id,
                    self._publisher_id,
                    safe_error,
                    delay,
                    self._max_attempts,
                )
                continue
            await self._repository.mark_published(
                record.id, self._publisher_id, published_at=datetime.now(UTC)
            )
            published += 1
        return published

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            count = await self.run_once()
            if count == 0:
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval)


_SECRET = re.compile(r"(?i)(password|secret|token|credential)\s*[=:]\s*[^\s,;]+")


def _safe_error(exc: Exception) -> str:
    text = _SECRET.sub(r"\1=<redacted>", str(exc)).replace("\n", " ")
    return f"{type(exc).__name__}: {text}"[:1000]
