"""Pydantic representation of ``infra/kafka/schemas/event-envelope.v1.json``."""

from __future__ import annotations

import re
from datetime import datetime
from app.compat import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+$")
_PRODUCER_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_RESOURCE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_SCHEMA_PATTERN = re.compile(r"^[a-z][a-z0-9.-]+\.v[1-9][0-9]*$")
_SENSITIVE_NAME = re.compile(
    r"password|secret|access_token|refresh_token|api_key|cccd|account_number|base64|ocr_text|pdf",
    re.IGNORECASE,
)


class ActorType(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    SERVICE = "SERVICE"
    AGENT = "AGENT"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Actor(_StrictModel):
    type: ActorType
    id: UUID


class Resource(_StrictModel):
    type: str
    id: UUID

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if not _RESOURCE_PATTERN.fullmatch(value):
            raise ValueError("resource type must use uppercase underscore notation")
        return value


class EventMetadata(_StrictModel):
    trace_id: UUID
    schema_name: str = Field(alias="schema", serialization_alias="schema", max_length=160)

    @field_validator("schema_name")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        if not _SCHEMA_PATTERN.fullmatch(value):
            raise ValueError("metadata.schema must be a versioned event schema name")
        return value


class EventEnvelope(_StrictModel):
    """Exact required envelope; payloads remain small references and status data."""

    event_id: UUID
    event_type: str = Field(max_length=128)
    event_version: int = Field(ge=1)
    occurred_at: datetime
    producer: str
    correlation_id: UUID
    causation_id: UUID | None
    partition_key: UUID
    actor: Actor
    resource: Resource
    payload: dict[str, Any]
    metadata: EventMetadata

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if not _EVENT_TYPE_PATTERN.fullmatch(value):
            raise ValueError("event_type does not follow the infrastructure contract")
        return value

    @field_validator("producer")
    @classmethod
    def validate_producer(cls, value: str) -> str:
        if not _PRODUCER_PATTERN.fullmatch(value):
            raise ValueError("producer must be a lowercase Kafka service identity")
        return value

    @field_validator("occurred_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 32:
            raise ValueError("event payload may contain at most 32 properties")
        forbidden = sorted(name for name in value if _SENSITIVE_NAME.search(name))
        if forbidden:
            raise ValueError(f"sensitive payload property names are forbidden: {', '.join(forbidden)}")
        return value

    def to_kafka_bytes(self) -> bytes:
        """Serialize using Pydantic's JSON-safe UUID/datetime representation."""

        return self.model_dump_json(exclude_none=False, by_alias=True).encode()
