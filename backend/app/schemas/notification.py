"""Employee notification contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.common import APIModel


class NotificationResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    employee_id: UUID
    notification_type: str
    title: str
    message: str
    resource_type: str | None = None
    resource_id: UUID | None = None
    status: str
    created_at: datetime
    read_at: datetime | None = None
