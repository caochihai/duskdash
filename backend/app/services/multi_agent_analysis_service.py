"""Application service for an authorized, in-memory multi-agent analysis run."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.agents.base import AgentInput, AgentName, AgentOutput
from app.agents.evaluation import (
    BoundedEvaluationCoordinator,
    EvaluationBatch,
    ExpertEvaluation,
)
from app.agents.orchestrator import AnalysisOrchestrator, AnalysisPlan
from app.agents.synthesizer import ReportSynthesizer, SynthesizedReport
from app.agents.validator import EvidenceValidator, ValidationOutcome


class _AnalysisServiceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MultiAgentAnalysisRequest(_AnalysisServiceModel):
    """Authorized contexts and persisted-reference allowlists for one analysis run."""

    document_input: AgentInput
    credit_input: AgentInput
    compliance_input: AgentInput
    authorized_source_ids: frozenset[UUID]
    valid_calculation_ids: frozenset[UUID]
    valid_policy_clause_ids: frozenset[UUID]


class MultiAgentAnalysisResult(_AnalysisServiceModel):
    """Decision-support artifacts; deliberately contains no loan-decision field."""

    analysis_case_id: UUID
    plan: AnalysisPlan
    document_output: AgentOutput
    credit_output: AgentOutput
    compliance_output: AgentOutput
    expert_evaluation: EvaluationBatch
    validation: ValidationOutcome
    report_writer_executed: bool
    report: SynthesizedReport | None
    human_decision_required: Literal[True] = True

    @property
    def expert_outputs(self) -> tuple[AgentOutput, AgentOutput, AgentOutput]:
        return self.document_output, self.credit_output, self.compliance_output


class ExpertExecutionResult(_AnalysisServiceModel):
    """Expert outputs before evaluator/validator/report-writer gates are applied."""

    analysis_case_id: UUID
    plan: AnalysisPlan
    document_output: AgentOutput
    credit_output: AgentOutput
    compliance_output: AgentOutput

    @property
    def expert_outputs(self) -> tuple[AgentOutput, AgentOutput, AgentOutput]:
        return self.document_output, self.credit_output, self.compliance_output


class AnalysisContextMismatchError(ValueError):
    """Raised before execution when expert inputs do not describe one resource scope."""


class MultiAgentAnalysisService:
    """Coordinate experts, deterministic validation, and draft-only synthesis."""

    def __init__(
        self,
        *,
        orchestrator: AnalysisOrchestrator,
        validator: EvidenceValidator,
        synthesizer: ReportSynthesizer,
        evaluation_coordinator: BoundedEvaluationCoordinator | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._validator = validator
        self._synthesizer = synthesizer
        self._evaluation_coordinator = (
            evaluation_coordinator or BoundedEvaluationCoordinator()
        )

    async def run(
        self,
        request: MultiAgentAnalysisRequest,
        *,
        retry_callback: Callable[
            [AgentOutput, ExpertEvaluation], Awaitable[AgentOutput]
        ]
        | None = None,
    ) -> MultiAgentAnalysisResult:
        """Run the complete gated flow without persisting or creating a loan decision."""

        execution = await self.execute_experts(request)
        evaluated_outputs, expert_evaluation = await self._evaluation_coordinator.run(
            execution.expert_outputs,
            authorized_source_ids=request.authorized_source_ids,
            valid_calculation_ids=request.valid_calculation_ids,
            valid_policy_clause_ids=request.valid_policy_clause_ids,
            retry_callback=retry_callback,
        )
        expert_outputs = _require_three_expert_outputs(evaluated_outputs)
        validation = await self.validate_experts(request, expert_outputs)
        report_writer_executed = (
            expert_evaluation.approved and validation.approved_for_synthesis
        )
        report = (
            await self.synthesize_report(
                expert_outputs,
                validation,
                expert_evaluation,
            )
            if report_writer_executed
            else None
        )

        document_output, credit_output, compliance_output = expert_outputs

        return MultiAgentAnalysisResult(
            analysis_case_id=execution.analysis_case_id,
            plan=execution.plan,
            document_output=document_output,
            credit_output=credit_output,
            compliance_output=compliance_output,
            expert_evaluation=expert_evaluation,
            validation=validation,
            report_writer_executed=report_writer_executed,
            report=report,
        )

    async def execute_experts(
        self, request: MultiAgentAnalysisRequest
    ) -> ExpertExecutionResult:
        """Stop before evaluation so a caller can gate the report writer."""

        _require_shared_context(request)
        _require_authorized_sources(request)

        plan = self._orchestrator.create_plan(request.document_input.analysis_case_id)
        outputs = await self._orchestrator.run_experts(
            document_input=request.document_input,
            credit_input=request.credit_input,
            compliance_input=request.compliance_input,
        )
        _require_expected_agents(outputs)

        document_output, credit_output, compliance_output = outputs
        return ExpertExecutionResult(
            analysis_case_id=request.document_input.analysis_case_id,
            plan=plan,
            document_output=document_output,
            credit_output=credit_output,
            compliance_output=compliance_output,
        )

    async def validate_experts(
        self,
        request: MultiAgentAnalysisRequest,
        outputs: tuple[AgentOutput, AgentOutput, AgentOutput],
    ) -> ValidationOutcome:
        """Validate only the evaluator-selected outputs against persisted allowlists."""

        _require_shared_context(request)
        _require_authorized_sources(request)
        _require_expected_agents(outputs)

        return await self._validator.validate(
            outputs,
            authorized_source_ids=request.authorized_source_ids,
            valid_calculation_ids=request.valid_calculation_ids,
            valid_policy_clause_ids=request.valid_policy_clause_ids,
        )

    async def synthesize_report(
        self,
        outputs: tuple[AgentOutput, AgentOutput, AgentOutput],
        validation: ValidationOutcome,
        expert_evaluation: EvaluationBatch,
    ) -> SynthesizedReport:
        """Invoke Report Writer only after evaluator and validator both allow it."""

        _require_expected_agents(outputs)
        if not expert_evaluation.approved:
            raise RuntimeError("Report Writer requires approved expert evaluation")
        if not validation.approved_for_synthesis:
            raise RuntimeError("Report Writer requires approved evidence validation")
        report = await self._synthesizer.synthesize(outputs, validation)
        _require_draft_report(report, validation)
        return report


def _require_shared_context(request: MultiAgentAnalysisRequest) -> None:
    inputs = {
        "credit_input": request.credit_input,
        "compliance_input": request.compliance_input,
    }
    expected = request.document_input
    mismatches = [
        f"{input_name}.{field_name}"
        for input_name, agent_input in inputs.items()
        for field_name in ("analysis_case_id", "customer_id", "loan_application_id")
        if getattr(agent_input, field_name) != getattr(expected, field_name)
    ]
    if mismatches:
        fields = ", ".join(mismatches)
        raise AnalysisContextMismatchError(
            f"All expert inputs must share analysis case, customer, and loan context; mismatched: {fields}"
        )


def _require_authorized_sources(request: MultiAgentAnalysisRequest) -> None:
    requested_source_ids = frozenset(
        source_id
        for agent_input in (
            request.document_input,
            request.credit_input,
            request.compliance_input,
        )
        for source_id in agent_input.authorized_source_ids
    )
    unauthorized = requested_source_ids - request.authorized_source_ids
    if unauthorized:
        raise PermissionError("Agent input contains sources outside the authorized analysis scope")


def _require_expected_agents(
    outputs: tuple[AgentOutput, AgentOutput, AgentOutput],
) -> None:
    expected = (AgentName.DOCUMENT, AgentName.CREDIT, AgentName.LEGAL_COMPLIANCE)
    actual = tuple(output.agent_name for output in outputs)
    if actual != expected:
        raise RuntimeError("Analysis orchestrator returned expert outputs in an invalid order")


def _require_three_expert_outputs(
    outputs: tuple[AgentOutput, ...],
) -> tuple[AgentOutput, AgentOutput, AgentOutput]:
    if len(outputs) != 3:
        raise RuntimeError("Analysis requires exactly three expert outputs")
    return outputs[0], outputs[1], outputs[2]


def _require_draft_report(
    report: SynthesizedReport,
    validation: ValidationOutcome,
) -> None:
    expected_status = "DRAFT" if validation.approved_for_synthesis else "INCOMPLETE"
    if report.status != expected_status:
        raise RuntimeError(
            "Report synthesizer must return DRAFT for validated output or INCOMPLETE otherwise"
        )
