from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents.base import AgentInput, CalculationReference, EvidenceRole
from app.agents.credit_agent import CreditAgent
from app.agents.document_agent import DocumentAgent
from app.agents.synthesizer import ReportSynthesizer
from app.agents.validator import EvidenceValidator


@pytest.mark.asyncio
async def test_document_agent_surfaces_completeness_indicators_and_evidence_conflicts() -> None:
    business_license_id = uuid4()
    tax_registration_id = uuid4()
    request = AgentInput(
        task_id=uuid4(),
        analysis_case_id=uuid4(),
        customer_id=uuid4(),
        authorized_source_ids=frozenset({business_license_id, tax_registration_id}),
        context={
            "assessment_date": "2026-07-18",
            "required_document_types": [
                "BUSINESS_LICENSE",
                "TAX_REGISTRATION",
                "BANK_STATEMENT",
            ],
            "required_document_indicators": {
                "BUSINESS_LICENSE": ["signature", "seal", "stamp"],
            },
            "documents": [
                {
                    "document_type": "BUSINESS_LICENSE",
                    "source_id": business_license_id,
                    "verification_status": "VERIFIED",
                    "expiry_date": "2025-12-31",
                    "presence_indicators": {
                        "signature": True,
                        "seal": False,
                        "stamp": True,
                    },
                    "extracted_fields": {"tax_code": "VN-001"},
                },
                {
                    "document_type": "TAX_REGISTRATION",
                    "source_id": tax_registration_id,
                    "verification_status": "PENDING",
                    "extracted_fields": {"tax_code": "VN-009"},
                },
            ],
        },
    )

    output = await DocumentAgent().run(request)

    finding_types = {finding.finding_type for finding in output.findings}
    assert {
        "MISSING_DOCUMENT",
        "EXPIRED_DOCUMENT",
        "UNVERIFIED_DOCUMENT",
        "DOCUMENT_INDICATOR_NOT_PRESENT",
        "CROSS_DOCUMENT_FIELD_CONFLICT",
    } <= finding_types
    assert output.missing_information == ("BANK_STATEMENT",)
    assert "MISSING_SEAL_INDICATOR" in output.risk_flags
    assert "CROSS_DOCUMENT_CONFLICT" in output.risk_flags
    assert output.contradictions == (
        "Field 'tax_code' has conflicting recorded values across BUSINESS_LICENSE, TAX_REGISTRATION.",
    )
    conflict = next(
        finding
        for finding in output.findings
        if finding.finding_type == "CROSS_DOCUMENT_FIELD_CONFLICT"
    )
    assert {item.source_id for item in conflict.evidence} == {
        business_license_id,
        tax_registration_id,
    }
    assert all(item.evidence_role is EvidenceRole.CONTRADICTING for item in conflict.evidence)
    assert "do not establish legal authenticity" in output.limitations[0]


class PersistedAffordabilityCalculator:
    def __init__(self, calculation_id: object) -> None:
        self.calculation_id = calculation_id

    async def calculate_for_analysis(
        self, request: AgentInput
    ) -> tuple[CalculationReference, ...]:
        return (
            CalculationReference(
                calculation_id=self.calculation_id,
                calculation_type="AFFORDABILITY",
                calculation_version="1.0",
                inputs={"existing_obligations": "15000000.0000"},
                result_value=Decimal("1.20"),
                result_payload={
                    "dti": "1.20",
                    "dscr": "0.83",
                    "net_disposable_income": "-2000000.0000",
                },
                unit="RATIO",
            ),
        )


@pytest.mark.asyncio
async def test_credit_agent_interprets_only_persisted_repayment_calculation() -> None:
    calculation_id = uuid4()
    agent = CreditAgent(PersistedAffordabilityCalculator(calculation_id))  # type: ignore[arg-type]
    output = await agent.run(
        AgentInput(
            task_id=uuid4(),
            analysis_case_id=uuid4(),
            customer_id=uuid4(),
        )
    )

    assert output.missing_information == ()
    assert {
        "NEGATIVE_NET_DISPOSABLE_INCOME",
        "DEBT_SERVICE_EXCEEDS_ACCEPTED_INCOME",
        "EXISTING_DEBT_OBLIGATIONS_PRESENT",
    } <= set(output.risk_flags)
    finding = next(
        item for item in output.findings if item.finding_type == "REPAYMENT_CAPACITY_RISK"
    )
    assert finding.calculation_ids == (calculation_id,)
    assert "persisted deterministic" in output.conclusion
    assert "no loan approval or rejection" in output.conclusion


@pytest.mark.asyncio
async def test_validator_and_report_surface_conflicts_missing_evidence_and_human_decision() -> None:
    business_license_id = uuid4()
    tax_registration_id = uuid4()
    calculation_id = uuid4()
    base = {
        "analysis_case_id": uuid4(),
        "customer_id": uuid4(),
    }
    document_output = await DocumentAgent().run(
        AgentInput(
            task_id=uuid4(),
            **base,
            authorized_source_ids=frozenset({business_license_id, tax_registration_id}),
            context={
                "required_document_types": ["BUSINESS_LICENSE", "BANK_STATEMENT"],
                "documents": [
                    {
                        "document_type": "BUSINESS_LICENSE",
                        "source_id": business_license_id,
                        "verification_status": "VERIFIED",
                        "extracted_fields": {"owner_name": "ACME ONE"},
                    },
                    {
                        "document_type": "TAX_REGISTRATION",
                        "source_id": tax_registration_id,
                        "verification_status": "VERIFIED",
                        "extracted_fields": {"owner_name": "ACME TWO"},
                    },
                ],
            },
        )
    )
    credit_output = await CreditAgent(
        PersistedAffordabilityCalculator(calculation_id)  # type: ignore[arg-type]
    ).run(AgentInput(task_id=uuid4(), **base))

    validation = await EvidenceValidator().validate(
        (document_output, credit_output),
        authorized_source_ids=frozenset({business_license_id, tax_registration_id}),
        valid_calculation_ids=frozenset({calculation_id}),
        valid_policy_clause_ids=frozenset(),
    )

    assert validation.validation_status == "INSUFFICIENT_EVIDENCE"
    assert not validation.approved_for_synthesis
    assert "DOCUMENT: BANK_STATEMENT" in validation.missing_information
    assert validation.agent_contradictions == document_output.contradictions
    assert "Required documents are missing" in validation.unsupported_claims

    report = await ReportSynthesizer().synthesize(
        (document_output, credit_output), validation
    )
    assert report.status == "INCOMPLETE"
    assert report.sections["DOCUMENT_VERIFICATION"]["findings"]
    repayment = report.sections["REPAYMENT_CAPACITY"]
    assert repayment["persisted_calculations"][0]["calculation_id"] == str(calculation_id)
    assert "NEGATIVE_NET_DISPOSABLE_INCOME" in repayment["risk_flags"]
    assert report.sections["CONTRADICTIONS"] == list(document_output.contradictions)
    assert "does not approve or reject" in report.sections["HUMAN_DECISION_NOTICE"]
    assert "loan:approve" in report.sections["HUMAN_DECISION_NOTICE"]
