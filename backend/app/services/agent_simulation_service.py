"""In-memory, deterministic multi-agent simulation for design and UI integration."""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import AgentOutput, CalculationReference, EvidenceReference, PolicyReference
from app.agents.compliance_agent import ComplianceAgent
from app.agents.credit_agent import CreditAgent
from app.agents.document_agent import DocumentAgent
from app.agents.evaluation import (
    EvaluationBatch,
    ExpertEvaluation,
    MockExpertEvaluationCoordinator,
)
from app.agents.mock_scenarios import (
    MockAnalysisRequestBundle,
    MockScenarioCode,
    MockScenarioSummary,
    build_mock_analysis_request,
    list_mock_scenarios,
)
from app.agents.orchestrator import AnalysisOrchestrator, AnalysisPlan
from app.agents.persisted_calculation_tool import PersistedCalculationTool
from app.agents.synthesizer import ReportClaimDraft, ReportSynthesizer, SynthesizedReport
from app.agents.validator import EvidenceValidator, ValidationOutcome
from app.services.multi_agent_analysis_service import MultiAgentAnalysisService


class _SimulationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NumberedCitation(_SimulationModel):
    number: int = Field(ge=1)
    token: str
    citation_type: Literal["EVIDENCE", "CALCULATION", "POLICY"]
    source_type: str
    source_id: UUID
    source_locator: dict[str, Any]
    quoted_text: str | None = None
    evidence_role: str | None = None
    retrieval_mode: Literal["INLINE_MOCK"] = "INLINE_MOCK"


class CitedReportClaim(_SimulationModel):
    section: str
    claim_text: str
    rendered_claim: str
    claim_type: str
    validation_status: str
    citation_numbers: tuple[int, ...]


class AgentSimulationResponse(_SimulationModel):
    """Read-only decision-support result; intentionally has no loan-decision field."""

    scenario_code: MockScenarioCode
    mode: Literal["MOCK"] = "MOCK"
    synthetic_data: Literal[True] = True
    display_notice: str
    scenario_title: str
    scenario_description: str
    objective: str
    customer_id: UUID
    loan_application_id: UUID
    analysis_case_id: UUID
    plan: AnalysisPlan
    expert_outputs: tuple[AgentOutput, AgentOutput, AgentOutput]
    validation: ValidationOutcome
    expert_evaluation: EvaluationBatch
    ready_for_human_review: bool
    report_writer_executed: bool
    report_status: Literal["DRAFT", "INCOMPLETE"]
    report: SynthesizedReport | None
    citations: tuple[NumberedCitation, ...]
    cited_claims: tuple[CitedReportClaim, ...]
    user_summary: str
    human_decision_notice: str
    human_decision_required: Literal[True] = True


class AgentSimulationService:
    """Run the real expert/orchestrator/validator code over synthetic scenario data.

    This service has no repository, event publisher, or loan-decision dependency.  It
    is therefore safe for an explicit design/demo endpoint but must be labelled MOCK.
    """

    def __init__(
        self,
        analysis_service: MultiAgentAnalysisService | None = None,
        evaluation_coordinator: MockExpertEvaluationCoordinator | None = None,
    ) -> None:
        self._analysis_service = analysis_service or _default_analysis_service()
        self._evaluation_coordinator = (
            evaluation_coordinator or MockExpertEvaluationCoordinator()
        )

    @staticmethod
    def list_scenarios() -> tuple[MockScenarioSummary, ...]:
        return list_mock_scenarios()

    async def run(
        self,
        scenario_code: MockScenarioCode | str,
        *,
        objective: str,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
    ) -> AgentSimulationResponse:
        bundle = build_mock_analysis_request(
            scenario_code,
            objective=objective,
            customer_id=customer_id,
            loan_application_id=loan_application_id,
        )
        execution = await self._analysis_service.execute_experts(bundle.request)
        evaluated_outputs, expert_evaluation = await self._evaluation_coordinator.run(
            execution.expert_outputs,
            authorized_source_ids=bundle.request.authorized_source_ids,
            valid_calculation_ids=bundle.request.valid_calculation_ids,
            valid_policy_clause_ids=bundle.request.valid_policy_clause_ids,
            retry_callback=_mock_feedback_round,
        )
        expert_outputs = _require_three_expert_outputs(evaluated_outputs)
        validation = await self._analysis_service.validate_experts(
            bundle.request,
            expert_outputs,
        )
        report_writer_executed = (
            expert_evaluation.approved and validation.approved_for_synthesis
        )
        report = (
            await self._analysis_service.synthesize_report(
                expert_outputs,
                validation,
                expert_evaluation,
            )
            if report_writer_executed
            else None
        )
        report_status: Literal["DRAFT", "INCOMPLETE"] = (
            "DRAFT" if report_writer_executed else "INCOMPLETE"
        )
        _require_expected_mock_outcome(bundle, report_status)
        ready_for_human_review = report_writer_executed
        citations, cited_claims = _number_citations(expert_outputs, report)
        human_notice = (
            "DỮ LIỆU MÔ PHỎNG. Báo cáo AI chỉ hỗ trợ phân tích, không phê duyệt hoặc từ chối "
            "khoản vay. Chỉ nhân viên có thẩm quyền loan:approve mới được xem xét bằng chứng và "
            "ghi quyết định chính thức."
        )
        return AgentSimulationResponse(
            scenario_code=bundle.summary.scenario_code,
            display_notice="DỮ LIỆU MÔ PHỎNG — KHÔNG PHẢI HỒ SƠ KHÁCH HÀNG THẬT",
            scenario_title=bundle.summary.title,
            scenario_description=bundle.summary.description,
            objective=bundle.objective,
            customer_id=bundle.customer_id,
            loan_application_id=bundle.loan_application_id,
            analysis_case_id=bundle.analysis_case_id,
            plan=execution.plan,
            expert_outputs=expert_outputs,
            validation=validation,
            expert_evaluation=expert_evaluation,
            ready_for_human_review=ready_for_human_review,
            report_writer_executed=report_writer_executed,
            report_status=report_status,
            report=report,
            citations=citations,
            cited_claims=cited_claims,
            user_summary=_user_summary(
                bundle,
                validation,
                cited_claims,
                ready_for_human_review=ready_for_human_review,
            ),
            human_decision_notice=human_notice,
        )


def _default_analysis_service() -> MultiAgentAnalysisService:
    orchestrator = AnalysisOrchestrator(
        document_agent=DocumentAgent(),
        credit_agent=CreditAgent(PersistedCalculationTool()),
        compliance_agent=ComplianceAgent(),
    )
    return MultiAgentAnalysisService(
        orchestrator=orchestrator,
        validator=EvidenceValidator(),
        synthesizer=ReportSynthesizer(),
    )


def _number_citations(
    outputs: tuple[AgentOutput, AgentOutput, AgentOutput],
    report: SynthesizedReport | None,
) -> tuple[tuple[NumberedCitation, ...], tuple[CitedReportClaim, ...]]:
    citations: list[NumberedCitation] = []
    number_by_key: dict[tuple[str, str, str], int] = {}
    calculation_number: dict[UUID, int] = {}
    policy_number: dict[UUID, int] = {}

    def add_evidence(reference: EvidenceReference) -> int:
        key = (
            "EVIDENCE",
            str(reference.source_id),
            f"{reference.source_type}:{_locator_key(reference.source_locator)}",
        )
        existing = number_by_key.get(key)
        if existing is not None:
            return existing
        number = len(citations) + 1
        citations.append(
            NumberedCitation(
                number=number,
                token=f"[{number}]",
                citation_type="EVIDENCE",
                source_type=reference.source_type,
                source_id=reference.source_id,
                source_locator=dict(reference.source_locator),
                quoted_text=reference.quoted_text,
                evidence_role=reference.evidence_role.value,
            )
        )
        number_by_key[key] = number
        return number

    def add_calculation(reference: CalculationReference) -> int:
        existing = calculation_number.get(reference.calculation_id)
        if existing is not None:
            return existing
        locator = {
            "resource": "mock.credit.calculation_record",
            "calculation_id": str(reference.calculation_id),
            "calculation_type": reference.calculation_type,
            "calculation_version": reference.calculation_version,
            "synthetic": True,
            "retrievable": False,
            "retrieval_mode": "INLINE_MOCK",
        }
        number = len(citations) + 1
        value = str(reference.result_value) if reference.result_value is not None else "null"
        citations.append(
            NumberedCitation(
                number=number,
                token=f"[{number}]",
                citation_type="CALCULATION",
                source_type="CALCULATION",
                source_id=reference.calculation_id,
                source_locator=locator,
                quoted_text=(
                    f"Phép tính mô phỏng {reference.calculation_type} có kết quả {value} "
                    f"{reference.unit or ''}."
                ).strip(),
            )
        )
        calculation_number[reference.calculation_id] = number
        return number

    def add_policy(reference: PolicyReference) -> int:
        existing = policy_number.get(reference.clause_id)
        if existing is not None:
            return existing
        locator = {
            "resource": "mock.policy.policy_clause",
            "policy_id": str(reference.policy_id),
            "policy_version_id": str(reference.policy_version_id),
            "clause_id": str(reference.clause_id),
            "clause_number": reference.clause_number,
            "effective_date": reference.effective_date,
            "synthetic": True,
            "retrievable": False,
            "retrieval_mode": "INLINE_MOCK",
        }
        number = len(citations) + 1
        citations.append(
            NumberedCitation(
                number=number,
                token=f"[{number}]",
                citation_type="POLICY",
                source_type="POLICY_CLAUSE",
                source_id=reference.clause_id,
                source_locator=locator,
                quoted_text=(
                    f"Điều khoản mô phỏng {reference.clause_number}, hiệu lực từ "
                    f"{reference.effective_date}."
                ),
            )
        )
        policy_number[reference.clause_id] = number
        return number

    for output in outputs:
        for reference in output.evidence_references:
            add_evidence(reference)
        for finding in output.findings:
            for reference in finding.evidence:
                add_evidence(reference)
        for calculation in output.calculations:
            add_calculation(calculation)
        for policy in output.policy_references:
            add_policy(policy)

    if report is None:
        return tuple(citations), ()

    findings = tuple(finding for output in outputs for finding in output.findings)
    if len(findings) != len(report.claims):
        raise RuntimeError("Mock report claims must retain a one-to-one mapping to expert findings")

    cited_claims: list[CitedReportClaim] = []
    for report_claim, finding in zip(report.claims, findings, strict=True):
        numbers = [add_evidence(reference) for reference in finding.evidence]
        numbers.extend(
            calculation_number[calculation_id]
            for calculation_id in finding.calculation_ids
            if calculation_id in calculation_number
        )
        numbers.extend(
            policy_number[clause_id]
            for clause_id in finding.policy_clause_ids
            if clause_id in policy_number
        )
        unique_numbers = tuple(dict.fromkeys(numbers))
        cited_claims.append(_cited_claim(report_claim, unique_numbers))
    return tuple(citations), tuple(cited_claims)


def _cited_claim(
    report_claim: ReportClaimDraft,
    citation_numbers: tuple[int, ...],
) -> CitedReportClaim:
    suffix = " ".join(f"[{number}]" for number in citation_numbers)
    rendered = f"{report_claim.claim_text} {suffix}".rstrip()
    return CitedReportClaim(
        section=report_claim.section,
        claim_text=report_claim.claim_text,
        rendered_claim=rendered,
        claim_type=report_claim.claim_type,
        validation_status=report_claim.validation_status,
        citation_numbers=citation_numbers,
    )


def _locator_key(locator: dict[str, Any]) -> str:
    return json.dumps(locator, sort_keys=True, separators=(",", ":"), default=str)


def _require_expected_mock_outcome(
    bundle: MockAnalysisRequestBundle,
    report_status: Literal["DRAFT", "INCOMPLETE"],
) -> None:
    if report_status != bundle.summary.expected_report_status:
        raise RuntimeError(
            "Mock scenario no longer produces its declared report status; update the fixture or agents"
        )


def _user_summary(
    bundle: MockAnalysisRequestBundle,
    validation: ValidationOutcome,
    claims: tuple[CitedReportClaim, ...],
    *,
    ready_for_human_review: bool,
) -> str:
    citation_tokens = " ".join(
        token
        for claim in claims
        for token in (f"[{number}]" for number in claim.citation_numbers)
    )
    unique_tokens = " ".join(dict.fromkeys(citation_tokens.split()))
    if ready_for_human_review:
        message = (
            "DỮ LIỆU MÔ PHỎNG: ba chuyên gia đã hoàn thành, validator chấp nhận các tham chiếu "
            "và hệ thống tạo báo cáo DRAFT để người có thẩm quyền xem xét."
        )
    else:
        message = (
            "DỮ LIỆU MÔ PHỎNG: evaluator hoặc validator phát hiện kết quả còn thiếu, mâu thuẫn "
            "hoặc chưa đủ bằng chứng; kết quả INCOMPLETE và Report Writer không được chạy."
        )
    references = f" Nguồn liên quan: {unique_tokens}." if unique_tokens else ""
    validation_note = f" Validator status: {validation.validation_status}."
    return f"{message}{references}{validation_note} Mục tiêu: {bundle.objective}"


async def _mock_feedback_round(
    output: AgentOutput,
    evaluation: ExpertEvaluation,
) -> AgentOutput:
    """Execute one auditable mock feedback round without inventing missing evidence."""

    if not evaluation.feedback:
        return output
    feedback_note = (
        "Mock evaluator feedback was acknowledged; unresolved issues require new authorized "
        "evidence or human review."
    )
    return output.model_copy(
        update={"limitations": tuple(dict.fromkeys((*output.limitations, feedback_note)))}
    )


def _require_three_expert_outputs(
    outputs: tuple[AgentOutput, ...],
) -> tuple[AgentOutput, AgentOutput, AgentOutput]:
    if len(outputs) != 3:
        raise RuntimeError("Mock analysis requires exactly three expert outputs")
    return outputs[0], outputs[1], outputs[2]
