"""Finding and evidence contracts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.common import APIModel, DecimalString


class FindingResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    analysis_case_id: UUID
    finding_type: str
    title: str
    description: str
    severity: str
    status: str
    confidence: DecimalString | None = None


class EvidenceResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    finding_id: UUID
    source_type: str
    source_id: UUID
    source_locator: dict[str, Any]
    quoted_text: str | None = None
    evidence_role: str

