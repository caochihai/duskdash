from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents.base import AgentInput, AgentName, AgentOutput
from app.agents.evaluation import BoundedEvaluationCoordinator, EvaluationBatch
from app.agents.orchestrator import AnalysisOrchestrator
from app.agents.synthesizer import ReportSynthesizer
from app.agents.validator import EvidenceValidator
from app.services.multi_agent_analysis_service import (
    AnalysisContextMismatchError,
    MultiAgentAnalysisRequest,
    MultiAgentAnalysisService,
)


class StubAgent:
    def __init__(
        self,
        name: AgentName,
        *,
        missing_information: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.missing_information = missing_information
        self.calls: list[AgentInput] = []

    async def run(self, request: AgentInput) -> AgentOutput:
        self.calls.append(request)
        return AgentOutput(
            agent_name=self.name,
            task_id=request.task_id,
            conclusion=f"{self.name.value} analysis completed without a loan decision.",
            missing_information=self.missing_information,
            recommended_action="Submit the analysis for authorized human review.",
            confidence=Decimal("0.9"),
        )


class StubEvaluationCoordinator(BoundedEvaluationCoordinator):
    def __init__(self, *, approved: bool) -> None:
        self.approved = approved

    async def run(self, outputs: tuple[AgentOutput, ...], **_: object):  # type: ignore[no-untyped-def]
        return outputs, EvaluationBatch(
            initial_evaluations=(),
            final_evaluations=(),
            retry_rounds_used=0,
            approved=self.approved,
        )


def _service(
    *,
    document_missing: tuple[str, ...] = (),
    evaluation_approved: bool = True,
) -> tuple[MultiAgentAnalysisService, StubAgent, StubAgent, StubAgent]:
    document = StubAgent(AgentName.DOCUMENT, missing_information=document_missing)
    credit = StubAgent(AgentName.CREDIT)
    compliance = StubAgent(AgentName.LEGAL_COMPLIANCE)
    orchestrator = AnalysisOrchestrator(
        document_agent=document,
        credit_agent=credit,
        compliance_agent=compliance,
    )
    return (
        MultiAgentAnalysisService(
            orchestrator=orchestrator,
            validator=EvidenceValidator(),
            synthesizer=ReportSynthesizer(),
            evaluation_coordinator=StubEvaluationCoordinator(
                approved=evaluation_approved
            ),
        ),
        document,
        credit,
        compliance,
    )


def _request(
    *,
    analysis_case_id: object | None = None,
    customer_id: object | None = None,
    loan_application_id: object | None = None,
) -> MultiAgentAnalysisRequest:
    case_id = analysis_case_id or uuid4()
    scoped_customer_id = customer_id or uuid4()
    scoped_loan_id = loan_application_id or uuid4()
    source_id = uuid4()
    shared = {
        "analysis_case_id": case_id,
        "customer_id": scoped_customer_id,
        "loan_application_id": scoped_loan_id,
        "authorized_source_ids": frozenset({source_id}),
    }
    return MultiAgentAnalysisRequest(
        document_input=AgentInput(task_id=uuid4(), **shared),
        credit_input=AgentInput(task_id=uuid4(), **shared),
        compliance_input=AgentInput(task_id=uuid4(), **shared),
        authorized_source_ids=frozenset({source_id}),
        valid_calculation_ids=frozenset(),
        valid_policy_clause_ids=frozenset(),
    )


@pytest.mark.asyncio
async def test_multi_agent_service_returns_validated_draft_requiring_human_decision() -> None:
    service, document, credit, compliance = _service()
    request = _request()

    result = await service.run(request)

    assert len(document.calls) == len(credit.calls) == len(compliance.calls) == 1
    assert result.analysis_case_id == request.document_input.analysis_case_id
    assert result.expert_evaluation.approved
    assert result.validation.approved_for_synthesis
    assert result.report_writer_executed
    assert result.report is not None
    assert result.report.status == "DRAFT"
    assert result.human_decision_required is True
    assert "decision" not in result.model_dump()
    assert "loan:approve" in result.report.sections["HUMAN_DECISION_NOTICE"]


@pytest.mark.asyncio
async def test_multi_agent_service_rejects_context_mismatch_before_agent_execution() -> None:
    service, document, credit, compliance = _service()
    request = _request()
    mismatched = request.model_copy(
        update={
            "compliance_input": request.compliance_input.model_copy(
                update={"loan_application_id": uuid4()}
            )
        }
    )

    with pytest.raises(AnalysisContextMismatchError, match=r"compliance_input\.loan_application_id"):
        await service.run(mismatched)

    assert not document.calls
    assert not credit.calls
    assert not compliance.calls


@pytest.mark.asyncio
async def test_missing_document_context_blocks_downstream_agents_and_report_writer() -> None:
    service, document, credit, compliance = _service(
        document_missing=("verified salary evidence",)
    )

    result = await service.run(_request())

    assert len(document.calls) == 1
    assert not credit.calls
    assert not compliance.calls
    assert result.credit_output.confidence == Decimal("0")
    assert result.compliance_output.missing_information == ("verified salary evidence",)
    assert not result.validation.approved_for_synthesis
    assert not result.report_writer_executed
    assert result.report is None
    assert result.human_decision_required is True


@pytest.mark.asyncio
async def test_rejected_expert_evaluation_blocks_report_writer() -> None:
    service, document, credit, compliance = _service(evaluation_approved=False)

    result = await service.run(_request())

    assert len(document.calls) == len(credit.calls) == len(compliance.calls) == 1
    assert not result.expert_evaluation.approved
    assert result.validation.approved_for_synthesis
    assert not result.report_writer_executed
    assert result.report is None
