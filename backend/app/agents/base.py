"""Strict input/output contracts shared by all expert agents."""

from __future__ import annotations

from decimal import Decimal
from app.compat import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentName(StrEnum):
    DOCUMENT = "DOCUMENT"
    CREDIT = "CREDIT"
    LEGAL_COMPLIANCE = "LEGAL_COMPLIANCE"


class EvidenceRole(StrEnum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"


class EvidenceReference(_AgentModel):
    source_type: str
    source_id: UUID
    source_locator: dict[str, Any] = Field(default_factory=dict)
    quoted_text: str | None = None
    evidence_role: EvidenceRole = EvidenceRole.SUPPORTING


class CalculationReference(_AgentModel):
    calculation_id: UUID
    calculation_type: str
    calculation_version: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    result_value: Decimal | None = None
    result_payload: dict[str, Any] = Field(default_factory=dict)
    unit: str | None = None


class PolicyReference(_AgentModel):
    policy_id: UUID
    policy_version_id: UUID
    clause_id: UUID
    clause_number: str
    effective_date: str


class FindingDraft(_AgentModel):
    finding_type: str
    title: str
    description: str
    severity: str
    status: str = "OPEN"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    recommended_action: str | None = None
    evidence: tuple[EvidenceReference, ...] = ()
    calculation_ids: tuple[UUID, ...] = ()
    policy_clause_ids: tuple[UUID, ...] = ()


class DownstreamReadiness(_AgentModel):
    """Typed dependency gate emitted by Document Agent for downstream experts."""

    credit_context_ready: bool
    compliance_context_ready: bool
    blockers: tuple[str, ...] = ()


class AgentInput(_AgentModel):
    task_id: UUID
    analysis_case_id: UUID
    customer_id: UUID
    loan_application_id: UUID | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    authorized_source_ids: frozenset[UUID] = frozenset()


class AgentOutput(_AgentModel):
    agent_name: AgentName
    task_id: UUID
    conclusion: str
    findings: tuple[FindingDraft, ...] = ()
    calculations: tuple[CalculationReference, ...] = ()
    evidence_references: tuple[EvidenceReference, ...] = ()
    policy_references: tuple[PolicyReference, ...] = ()
    downstream_readiness: DownstreamReadiness | None = None
    assumptions: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    recommended_action: str
    confidence: Decimal = Field(ge=0, le=1)


class Agent(Protocol):
    name: AgentName

    async def run(self, request: AgentInput) -> AgentOutput: ...
