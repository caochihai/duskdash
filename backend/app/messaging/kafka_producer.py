"""Least-privilege aiokafka producer for validated infrastructure events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiokafka import AIOKafkaProducer

from app.messaging.event_envelope import EventEnvelope
from app.messaging.kafka_consumer import JobStatusSnapshot
from app.messaging.topic_registry import TOPIC_SPECS, Topic, TopicRegistry


@dataclass(frozen=True, slots=True)
class PublishMetadata:
    topic: str
    partition: int
    offset: int


class KafkaEventProducer:
    """One producer instance for one exact non-admin SCRAM principal."""

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        principal: str,
        password: str,
        client_id: str | None = None,
        security_protocol: str = "SASL_PLAINTEXT",
        sasl_mechanism: str = "SCRAM-SHA-512",
        producer: Any | None = None,
    ) -> None:
        if principal not in {
            "bank-api",
            "document-worker",
            "analysis-orchestrator",
            "credit-worker",
            "compliance-worker",
            "report-worker",
            "notification-gateway",
            "audit-consumer",
        }:
            raise ValueError("unknown or administrative Kafka runtime principal")
        if not password:
            raise ValueError("Kafka SCRAM password is required")
        self.principal = principal
        self._producer = producer
        self._configuration = {
            "bootstrap_servers": bootstrap_servers,
            "client_id": client_id or principal,
            "security_protocol": security_protocol,
            "sasl_mechanism": sasl_mechanism,
            "sasl_plain_username": principal,
            "sasl_plain_password": password,
            "acks": "all",
            "enable_idempotence": True,
            "max_request_size": 1_048_576,
        }
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        if self._producer is None:
            self._producer = AIOKafkaProducer(**self._configuration)
        await self._producer.start()
        self._started = True

    async def stop(self) -> None:
        if self._producer is not None and self._started:
            await self._producer.stop()
        self._started = False

    async def send_envelope(self, envelope: EventEnvelope, *, topic: Topic | str | None = None) -> PublishMetadata:
        if envelope.producer != self.principal:
            raise ValueError(
                f"event producer {envelope.producer} does not match SCRAM principal {self.principal}"
            )
        selected = TopicRegistry.topic_for_event(envelope.event_type) if topic is None else Topic(topic)
        TopicRegistry.assert_can_produce(self.principal, selected)
        TopicRegistry.validate_event_topic(
            envelope.event_type,
            envelope.resource.type,
            envelope.metadata.schema_name,
            selected,
        )
        payload = envelope.to_kafka_bytes()
        if len(payload) > TOPIC_SPECS[selected].max_message_bytes:
            raise ValueError("Kafka event exceeds the 1 MiB infrastructure limit")
        if not self._started or self._producer is None:
            raise RuntimeError("Kafka producer has not been started")
        result = await self._producer.send_and_wait(
            selected.value,
            key=str(envelope.partition_key).encode(),
            value=payload,
            headers=[
                ("event_type", envelope.event_type.encode()),
                ("correlation_id", str(envelope.correlation_id).encode()),
                ("trace_id", str(envelope.metadata.trace_id).encode()),
                ("schema", envelope.metadata.schema_name.encode()),
            ],
        )
        return PublishMetadata(topic=result.topic, partition=result.partition, offset=result.offset)

    async def send_job_status(self, snapshot: JobStatusSnapshot) -> PublishMetadata:
        topic = TopicRegistry.assert_can_produce(self.principal, Topic.JOB_STATUS)
        payload = snapshot.model_dump_json().encode()
        if not self._started or self._producer is None:
            raise RuntimeError("Kafka producer has not been started")
        result = await self._producer.send_and_wait(
            topic.value,
            key=str(snapshot.job_id).encode(),
            value=payload,
            headers=[("schema", b"job.status.v1")],
        )
        return PublishMetadata(topic=result.topic, partition=result.partition, offset=result.offset)

    async def __aenter__(self) -> KafkaEventProducer:
        await self.start()
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.stop()
