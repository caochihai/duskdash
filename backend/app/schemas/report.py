"""Report request, claim, and review contracts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.common import APIModel, DecimalString


class ReportRequest(APIModel):
    report_type: str = Field(default="CREDIT_ASSESSMENT", min_length=1, max_length=30)


class ReportReviewRequest(APIModel):
    status: str
    review_note: str | None = Field(default=None, max_length=2000)


class ReportResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    analysis_case_id: UUID
    report_type: str
    status: str
    version_number: int
    json_payload: dict[str, Any]


class ReportClaimResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    report_id: UUID
    section: str
    claim_text: str
    claim_type: str
    confidence: DecimalString | None = None
    validation_status: str

