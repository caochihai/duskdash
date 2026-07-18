"""Build a structured report draft; never create a loan decision."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import AgentOutput
from app.agents.validator import ValidationOutcome


class ReportClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section: str
    claim_text: str
    claim_type: str
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    validation_status: str
    evidence_source_ids: tuple[UUID, ...] = ()
    calculation_ids: tuple[UUID, ...] = ()
    policy_clause_ids: tuple[UUID, ...] = ()


class SynthesizedReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    sections: dict[str, Any]
    claims: tuple[ReportClaimDraft, ...]


class ReportSynthesizer:
    async def synthesize(
        self, outputs: tuple[AgentOutput, ...], validation: ValidationOutcome
    ) -> SynthesizedReport:
        claims = tuple(
            ReportClaimDraft(
                section="KEY_RISKS" if finding.severity in {"HIGH", "CRITICAL"} else "POSITIVE_FACTORS",
                claim_text=finding.description,
                claim_type=finding.finding_type,
                confidence=finding.confidence,
                validation_status=validation.validation_status,
                evidence_source_ids=tuple(reference.source_id for reference in finding.evidence),
                calculation_ids=finding.calculation_ids,
                policy_clause_ids=finding.policy_clause_ids,
            )
            for output in outputs
            for finding in output.findings
        )
        sections: dict[str, Any] = {
            "EXECUTIVE_SUMMARY": [output.conclusion for output in outputs],
            "DOCUMENT_STATUS": _agent_section(outputs, "DOCUMENT"),
            "FINANCIAL_ANALYSIS": _agent_section(outputs, "CREDIT"),
            "DOCUMENT_VERIFICATION": _document_verification(outputs),
            "REPAYMENT_CAPACITY": _repayment_capacity(outputs),
            "POLICY_CHECK": _agent_section(outputs, "LEGAL_COMPLIANCE"),
            "POSITIVE_FACTORS": [
                claim.claim_text for claim in claims if claim.section == "POSITIVE_FACTORS"
            ],
            "KEY_RISKS": [claim.claim_text for claim in claims if claim.section == "KEY_RISKS"],
            "CONTRADICTIONS": _unique_strings(
                (
                    *(item for output in outputs for item in output.contradictions),
                    *validation.agent_contradictions,
                )
            ),
            "MISSING_INFORMATION": _unique_strings(
                (
                    *(item for output in outputs for item in output.missing_information),
                    *validation.missing_information,
                )
            ),
            "REQUIRED_CONDITIONS": _unique_strings(
                tuple(
                    finding.recommended_action
                    for output in outputs
                    for finding in output.findings
                    if finding.recommended_action
                )
            ),
            "LIMITATIONS": [item for output in outputs for item in output.limitations],
            "HUMAN_DECISION_NOTICE": (
                "This AI-generated report is decision support only and does not approve or reject a "
                "loan. Only an authorized employee with loan:approve authority may review the cited "
                "evidence and record an official decision."
            ),
        }
        return SynthesizedReport(
            status="DRAFT" if validation.approved_for_synthesis else "INCOMPLETE",
            sections=sections,
            claims=claims,
        )


def _agent_section(outputs: tuple[AgentOutput, ...], agent_name: str) -> list[str]:
    return [
        finding.description
        for output in outputs
        if output.agent_name.value == agent_name
        for finding in output.findings
    ]


def _document_verification(outputs: tuple[AgentOutput, ...]) -> dict[str, Any]:
    document_outputs = [output for output in outputs if output.agent_name.value == "DOCUMENT"]
    return {
        "summary": [output.conclusion for output in document_outputs],
        "findings": [
            {
                "type": finding.finding_type,
                "description": finding.description,
                "severity": finding.severity,
                "evidence_source_ids": [str(item.source_id) for item in finding.evidence],
            }
            for output in document_outputs
            for finding in output.findings
        ],
        "risk_flags": _unique_strings(
            tuple(flag for output in document_outputs for flag in output.risk_flags)
        ),
        "authenticity_notice": (
            "Recorded signature, seal, and stamp presence signals do not establish legal authenticity."
        ),
    }


def _repayment_capacity(outputs: tuple[AgentOutput, ...]) -> dict[str, Any]:
    credit_outputs = [output for output in outputs if output.agent_name.value == "CREDIT"]
    return {
        "summary": [output.conclusion for output in credit_outputs],
        "persisted_calculations": [
            {
                "calculation_id": str(calculation.calculation_id),
                "calculation_type": calculation.calculation_type,
                "calculation_version": calculation.calculation_version,
                "result_value": (
                    str(calculation.result_value) if calculation.result_value is not None else None
                ),
                "result_payload": {
                    key: str(value) if isinstance(value, Decimal) else value
                    for key, value in calculation.result_payload.items()
                },
                "unit": calculation.unit,
            }
            for output in credit_outputs
            for calculation in output.calculations
        ],
        "risk_flags": _unique_strings(
            tuple(flag for output in credit_outputs for flag in output.risk_flags)
        ),
        "decision_notice": "Repayment indicators require policy checks and an authorized human decision.",
    }


def _unique_strings(values: tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(values))
