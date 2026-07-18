"""Notification consumer and Redis SSE fan-out entry point."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.cache.pubsub import RedisPubSub, SSEChannels
from app.messaging.event_envelope import EventEnvelope
from app.messaging.kafka_consumer import JobStatusSnapshot
from app.messaging.topic_registry import Topic
from app.workers.runtime import WorkerSpec, run_cli

SPEC = WorkerSpec(
    name="notification-gateway",
    principal="notification-gateway",
    group_id="notification-gateway-group",
    topics=frozenset({Topic.NOTIFICATION_EVENTS, Topic.JOB_STATUS}),
    handled_event_types=frozenset(
        {"job.progress.updated", "job.completed", "job.failed", "notification.created"}
    ),
)


class NotificationWorkRepository(Protocol):
    async def persist_from_event(self, event: EventEnvelope) -> UUID | None: ...


class NotificationWorker:
    def __init__(self, repository: NotificationWorkRepository, pubsub: RedisPubSub) -> None:
        self._repository = repository
        self._pubsub = pubsub

    async def handle(self, event: EventEnvelope) -> UUID | None:
        if event.event_type not in SPEC.handled_event_types:
            return None
        notification_id = await self._repository.persist_from_event(event)
        signal: dict[str, Any] = dict(event.payload)
        signal.setdefault("status", event.event_type.rsplit(".", 1)[-1].upper())
        job_id = _uuid_value(event.payload.get("job_id"))
        employee_id = _uuid_value(event.payload.get("employee_id"))
        if job_id:
            await self._pubsub.publish(SSEChannels.job(job_id), signal)
        if employee_id:
            await self._pubsub.publish(SSEChannels.employee(employee_id), signal)
        return notification_id

    async def handle_snapshot(self, snapshot: JobStatusSnapshot) -> None:
        await self._pubsub.publish(
            SSEChannels.job(snapshot.job_id),
            {
                "job_id": snapshot.job_id,
                "status": snapshot.status,
                "progress_percent": snapshot.progress_percent,
                "current_step": snapshot.current_step,
            },
        )


def _uuid_value(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def main() -> None:
    run_cli("notification_worker", SPEC)


if __name__ == "__main__":
    main()
