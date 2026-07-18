from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.messaging.event_envelope import Actor, ActorType, EventEnvelope, EventMetadata, Resource
from app.messaging.kafka_consumer import KafkaEventConsumer
from app.messaging.kafka_producer import KafkaEventProducer
from app.messaging.outbox_publisher import OutboxPublisher
from app.messaging.topic_registry import Topic, TopicContractError, TopicRegistry


def event(**updates: Any) -> EventEnvelope:
    values: dict[str, Any] = {
        "event_id": uuid4(),
        "event_type": "document.processing.requested",
        "event_version": 1,
        "occurred_at": datetime.now(UTC),
        "producer": "bank-api",
        "correlation_id": uuid4(),
        "causation_id": None,
        "partition_key": uuid4(),
        "actor": Actor(type=ActorType.EMPLOYEE, id=uuid4()),
        "resource": Resource(type="DOCUMENT_VERSION", id=uuid4()),
        "payload": {"job_id": str(uuid4())},
        "metadata": EventMetadata(trace_id=uuid4(), schema="document.processing.requested.v1"),
    }
    values.update(updates)
    return EventEnvelope(**values)


def test_event_envelope_and_topic_acl_are_strict() -> None:
    envelope = event()
    assert TopicRegistry.topic_for_event(envelope.event_type) is Topic.DOCUMENT_COMMANDS
    TopicRegistry.assert_can_produce("bank-api", Topic.DOCUMENT_COMMANDS)
    with pytest.raises(TopicContractError):
        TopicRegistry.assert_can_produce("bank-api", Topic.DOCUMENT_EVENTS)
    with pytest.raises(ValidationError):
        event(payload={"access_token": "forbidden"})


def test_consumer_requires_exact_acl_group() -> None:
    with pytest.raises(TopicContractError):
        KafkaEventConsumer(
            bootstrap_servers="localhost:29092",
            principal="credit-worker",
            password="secret",
            group_id="credit-worker-test-group",
            topics=[Topic.ANALYSIS_COMMANDS],
        )


class FakeKafkaProducer:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send_and_wait(self, topic: str, **kwargs: object) -> object:
        self.sent.append({"topic": topic, **kwargs})
        return SimpleNamespace(topic=topic, partition=0, offset=7)


@pytest.mark.asyncio
async def test_kafka_producer_serializes_partition_key() -> None:
    fake = FakeKafkaProducer()
    producer = KafkaEventProducer(
        bootstrap_servers="localhost:29092",
        principal="bank-api",
        password="secret",
        producer=fake,
    )
    await producer.start()
    envelope = event()
    result = await producer.send_envelope(envelope)
    assert result.topic == Topic.DOCUMENT_COMMANDS
    assert fake.sent[0]["key"] == str(envelope.partition_key).encode()


class FakeOutboxRepository:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row
        self.published: list[UUID] = []

    async def claim_pending_for_producer(self, **kwargs: object) -> list[dict[str, Any]]:
        assert kwargs["producer"] == "bank-api"
        return [self.row]

    async def mark_published(
        self, event_id: UUID, publisher_id: str, published_at: datetime | None = None
    ) -> None:
        self.published.append(event_id)

    async def mark_failed(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("mark_failed was not expected")


class FakeEnvelopeProducer:
    principal = "bank-api"

    def __init__(self) -> None:
        self.topics: list[str | None] = []

    async def send_envelope(
        self, envelope: EventEnvelope, *, topic: str | None = None
    ) -> object:
        self.topics.append(topic)
        return object()


@pytest.mark.asyncio
async def test_outbox_reads_full_envelope_payload_and_explicit_topic_header() -> None:
    envelope = event()
    row = {
        "id": envelope.event_id,
        "aggregate_type": envelope.resource.type,
        "aggregate_id": envelope.resource.id,
        "event_type": envelope.event_type,
        "event_version": envelope.event_version,
        "partition_key": str(envelope.partition_key),
        "payload": envelope.model_dump(mode="json"),
        "headers": {"topic": Topic.DOCUMENT_COMMANDS.value},
        "attempt_count": 0,
        "created_at": envelope.occurred_at,
    }
    repository = FakeOutboxRepository(row)
    producer = FakeEnvelopeProducer()
    publisher = OutboxPublisher(repository, producer, publisher_id="publisher-1")  # type: ignore[arg-type]
    assert await publisher.run_once() == 1
    assert producer.topics == [Topic.DOCUMENT_COMMANDS.value]
    assert repository.published == [envelope.event_id]
