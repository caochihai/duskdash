from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents.base import (
    AgentInput,
    AgentName,
    AgentOutput,
    CalculationReference,
    EvidenceReference,
    FindingDraft,
)
from app.agents.compliance_agent import ComplianceAgent
from app.agents.context_router import ContextRouter, RoutingRequest
from app.agents.credit_agent import CreditAgent
from app.agents.document_agent import DocumentAgent
from app.agents.orchestrator import AnalysisOrchestrator, TaskCode
from app.agents.synthesizer import ReportSynthesizer
from app.agents.validator import EvidenceValidator


@pytest.mark.asyncio
async def test_context_router_authorizes_before_semantic_routing() -> None:
    with pytest.raises(PermissionError):
        await ContextRouter().route(
            RoutingRequest(
                employee_id=uuid4(),
                message="calculate DTI",
                active_customer_id=uuid4(),
                accessible_customer_ids=frozenset(),
            )
        )


class FakeCalculator:
    def __init__(self, calculation_id: object) -> None:
        self.calculation_id = calculation_id

    async def calculate_for_analysis(
        self, request: AgentInput
    ) -> tuple[CalculationReference, ...]:
        return (
            CalculationReference(
                calculation_id=self.calculation_id,
                calculation_type="DTI",
                result_value=Decimal("0.42"),
                unit="RATIO",
            ),
        )


@pytest.mark.asyncio
async def test_orchestrator_enforces_document_dependency_and_builds_task_graph() -> None:
    calculation_id = uuid4()
    document = DocumentAgent()
    credit = CreditAgent(FakeCalculator(calculation_id))  # type: ignore[arg-type]
    compliance = ComplianceAgent()
    orchestrator = AnalysisOrchestrator(
        document_agent=document,
        credit_agent=credit,
        compliance_agent=compliance,
    )
    case_id = uuid4()
    plan = orchestrator.create_plan(case_id)
    tasks = {task.task_code: task for task in plan.tasks}
    assert tasks[TaskCode.CREDIT_ASSESSMENT].depends_on == (
        tasks[TaskCode.DOCUMENT_REVIEW].id,
    )
    assert set(tasks[TaskCode.VALIDATION].depends_on) == {
        tasks[TaskCode.CREDIT_ASSESSMENT].id,
        tasks[TaskCode.POLICY_CHECK].id,
    }

    base = {
        "analysis_case_id": case_id,
        "customer_id": uuid4(),
    }
    document_input = AgentInput(
        task_id=uuid4(),
        **base,
        context={"required_document_types": ["SALARY_SLIP"], "available_document_types": []},
    )
    outputs = await orchestrator.run_experts(
        document_input=document_input,
        credit_input=AgentInput(task_id=uuid4(), **base),
        compliance_input=AgentInput(task_id=uuid4(), **base),
    )
    assert outputs[1].confidence == Decimal("0")
    assert outputs[2].missing_information == (
        "required document type is missing: SALARY_SLIP",
    )


@pytest.mark.asyncio
async def test_validator_checks_evidence_ownership_and_synthesizer_keeps_human_notice() -> None:
    source_id = uuid4()
    evidence = EvidenceReference(
        source_type="DOCUMENT_FIELD",
        source_id=source_id,
        source_locator={"field": "monthly_income"},
    )
    output = AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=uuid4(),
        conclusion="Evidence-backed finding.",
        findings=(
            FindingDraft(
                finding_type="DOCUMENT_STATUS",
                title="Verified source",
                description="A reviewed source is available.",
                severity="LOW",
                confidence=Decimal("0.9"),
                evidence=(evidence,),
            ),
        ),
        evidence_references=(evidence,),
        recommended_action="Continue human review.",
        confidence=Decimal("0.9"),
    )
    validator = EvidenceValidator()
    denied = await validator.validate(
        (output,),
        authorized_source_ids=frozenset(),
        valid_calculation_ids=frozenset(),
        valid_policy_clause_ids=frozenset(),
    )
    assert not denied.approved_for_synthesis
    approved = await validator.validate(
        (output,),
        authorized_source_ids=frozenset({source_id}),
        valid_calculation_ids=frozenset(),
        valid_policy_clause_ids=frozenset(),
    )
    assert approved.approved_for_synthesis
    report = await ReportSynthesizer().synthesize((output,), approved)
    assert report.status == "DRAFT"
    assert "loan:approve" in report.sections["HUMAN_DECISION_NOTICE"]
