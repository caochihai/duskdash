"""Background job, step, history, and SSE contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.common import APIModel


class JobResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    job_type: str
    resource_type: str
    resource_id: UUID
    status: str
    progress_percent: int
    current_step: str | None = None
    correlation_id: UUID


class JobStepResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    job_id: UUID
    step_code: str
    step_order: int
    status: str
    progress_percent: int


class JobEventResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: int
    job_id: UUID
    event_type: str
    sequence_number: int
    payload: dict[str, Any]
    created_at: datetime

