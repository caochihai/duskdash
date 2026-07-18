"""Audit projection consumer; does not produce business commands."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.messaging.event_envelope import EventEnvelope
from app.messaging.topic_registry import Topic
from app.workers.runtime import WorkerSpec, run_cli

SPEC = WorkerSpec(
    name="audit-consumer",
    principal="audit-consumer",
    group_id="audit-consumer-group",
    topics=frozenset(
        {Topic.AUDIT_EVENTS, Topic.DOCUMENT_EVENTS, Topic.ANALYSIS_EVENTS, Topic.REPORT_EVENTS}
    ),
    handled_event_types=frozenset(),
)


class AuditProjectionRepository(Protocol):
    async def project(self, event: EventEnvelope) -> UUID | None: ...


class AuditConsumer:
    def __init__(self, repository: AuditProjectionRepository) -> None:
        self._repository = repository

    async def handle(self, event: EventEnvelope) -> UUID | None:
        return await self._repository.project(event)


def main() -> None:
    run_cli("audit_consumer", SPEC)


if __name__ == "__main__":
    main()
