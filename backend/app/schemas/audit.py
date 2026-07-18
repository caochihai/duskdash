"""Append-only audit event response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.common import APIModel


class AuditEventResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: UUID
    event_time: datetime
    actor_type: str
    actor_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: UUID | None = None
    customer_id: UUID | None = None
    loan_application_id: UUID | None = None
    result: str
    request_id: UUID | None = None
    correlation_id: UUID | None = None
    metadata: dict[str, Any]
    previous_hash: str | None = None
    event_hash: str
