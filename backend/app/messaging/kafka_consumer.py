"""Sequential aiokafka consumer that leaves offset commits to the worker."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from datetime import datetime
from app.compat import StrEnum
from typing import Any
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.messaging.event_envelope import EventEnvelope
from app.messaging.topic_registry import TOPIC_SPECS, Topic, TopicRegistry


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PUBLISHED = "PUBLISHED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobStatusSnapshot(BaseModel):
    """Compacted value stored on ``bank.job-status.v1`` under ``job_id``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    status: JobStatus
    progress_percent: int = Field(ge=0, le=100)
    current_step: str | None = None
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return value


class ConsumedMessage(BaseModel):
    """Parsed message plus Kafka coordinates used for diagnostics."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    topic: Topic
    partition: int
    offset: int
    timestamp_ms: int
    key: bytes | None
    payload: EventEnvelope | JobStatusSnapshot
    raw: Any = Field(exclude=True)


class KafkaEventConsumer:
    """One exact ACL-bound consumer; automatic offset commits are prohibited."""

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        principal: str,
        password: str,
        group_id: str,
        topics: Iterable[Topic | str],
        client_id: str | None = None,
        security_protocol: str = "SASL_PLAINTEXT",
        sasl_mechanism: str = "SCRAM-SHA-512",
        auto_offset_reset: str = "earliest",
        consumer: Any | None = None,
    ) -> None:
        selected = frozenset(Topic(topic) for topic in topics)
        if not selected:
            raise ValueError("Kafka consumer requires at least one topic")
        TopicRegistry.assert_can_consume(principal, group_id, selected)
        if not password:
            raise ValueError("Kafka SCRAM password is required")
        self.principal = principal
        self.group_id = group_id
        self.topics = selected
        self._consumer = consumer
        self._configuration = {
            "bootstrap_servers": bootstrap_servers,
            "client_id": client_id or principal,
            "group_id": group_id,
            "security_protocol": security_protocol,
            "sasl_mechanism": sasl_mechanism,
            "sasl_plain_username": principal,
            "sasl_plain_password": password,
            "enable_auto_commit": False,
            "auto_offset_reset": auto_offset_reset,
            "max_partition_fetch_bytes": 1_048_576,
        }
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        if self._consumer is None:
            self._consumer = AIOKafkaConsumer(
                *(topic.value for topic in sorted(self.topics, key=str)), **self._configuration
            )
        await self._consumer.start()
        self._started = True

    async def stop(self) -> None:
        if self._consumer is not None and self._started:
            await self._consumer.stop()
        self._started = False

    async def messages(self) -> AsyncIterator[ConsumedMessage]:
        if not self._started or self._consumer is None:
            raise RuntimeError("Kafka consumer has not been started")
        async for raw in self._consumer:
            topic = Topic(raw.topic)
            if len(raw.value) > TOPIC_SPECS[topic].max_message_bytes:
                raise ValueError("Kafka message exceeds the infrastructure limit")
            if topic is Topic.JOB_STATUS:
                snapshot = JobStatusSnapshot.model_validate_json(raw.value)
                payload: EventEnvelope | JobStatusSnapshot = snapshot
                expected_key = str(snapshot.job_id).encode()
            else:
                envelope = EventEnvelope.model_validate_json(raw.value)
                payload = envelope
                TopicRegistry.validate_event_topic(
                    envelope.event_type,
                    envelope.resource.type,
                    envelope.metadata.schema_name,
                    topic,
                )
                expected_key = str(envelope.partition_key).encode()
            if raw.key != expected_key:
                raise ValueError("Kafka record key does not match the contracted partition key")
            yield ConsumedMessage(
                topic=topic,
                partition=raw.partition,
                offset=raw.offset,
                timestamp_ms=raw.timestamp,
                key=raw.key,
                payload=payload,
                raw=raw,
            )

    async def commit(self) -> None:
        """Commit only after Inbox and the business transaction succeed."""

        if not self._started or self._consumer is None:
            raise RuntimeError("Kafka consumer has not been started")
        await self._consumer.commit()

    async def __aenter__(self) -> KafkaEventConsumer:
        await self.start()
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.stop()
