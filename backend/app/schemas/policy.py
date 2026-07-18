"""Policy and effective clause contracts."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.common import APIModel


class PolicyResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    policy_code: str
    policy_name: str
    policy_type: str
    status: str


class PolicyClauseResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID | None = None
    clause_id: UUID | None = None
    policy_version_id: UUID
    clause_number: str
    title: str | None = None
    content: str
    effective_from: date
    effective_until: date | None = None

