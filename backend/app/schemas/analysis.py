"""Analysis case and structured agent response contracts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.common import APIModel, DecimalString


class AnalysisCaseResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    case_type: str
    customer_id: UUID
    loan_application_id: UUID | None = None
    status: str
    objective: str
    correlation_id: UUID
    job_id: UUID | None = None


class AgentOutput(APIModel):
    agent_name: str
    task_id: UUID
    conclusion: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_references: list[dict[str, Any]] = Field(default_factory=list)
    policy_references: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_action: str
    confidence: DecimalString

