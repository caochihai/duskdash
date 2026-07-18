"""Idempotent analysis task graph and expert execution ordering."""

from __future__ import annotations

import asyncio
from app.compat import StrEnum
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict

from app.agents.base import Agent, AgentInput, AgentOutput


class TaskCode(StrEnum):
    DOCUMENT_REVIEW = "DOCUMENT_REVIEW"
    CREDIT_ASSESSMENT = "CREDIT_ASSESSMENT"
    POLICY_CHECK = "POLICY_CHECK"
    VALIDATION = "VALIDATION"
    SYNTHESIS = "SYNTHESIS"
    REPORT_GENERATION = "REPORT_GENERATION"


class AnalysisTaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    task_code: TaskCode
    agent_type: str
    objective: str
    depends_on: tuple[UUID, ...]


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_case_id: UUID
    tasks: tuple[AnalysisTaskPlan, ...]


class AnalysisOrchestrator:
    def __init__(self, *, document_agent: Agent, credit_agent: Agent, compliance_agent: Agent) -> None:
        self._document = document_agent
        self._credit = credit_agent
        self._compliance = compliance_agent

    def create_plan(self, analysis_case_id: UUID) -> AnalysisPlan:
        task_ids = {code: uuid5(analysis_case_id, code.value) for code in TaskCode}
        tasks = (
            AnalysisTaskPlan(
                id=task_ids[TaskCode.DOCUMENT_REVIEW],
                task_code=TaskCode.DOCUMENT_REVIEW,
                agent_type="DOCUMENT",
                objective="Review document completeness, verification, and contradictions.",
                depends_on=(),
            ),
            AnalysisTaskPlan(
                id=task_ids[TaskCode.CREDIT_ASSESSMENT],
                task_code=TaskCode.CREDIT_ASSESSMENT,
                agent_type="CREDIT",
                objective="Interpret deterministic affordability calculations.",
                depends_on=(task_ids[TaskCode.DOCUMENT_REVIEW],),
            ),
            AnalysisTaskPlan(
                id=task_ids[TaskCode.POLICY_CHECK],
                task_code=TaskCode.POLICY_CHECK,
                agent_type="LEGAL_COMPLIANCE",
                objective="Check effective approved policy clauses.",
                depends_on=(task_ids[TaskCode.DOCUMENT_REVIEW],),
            ),
            AnalysisTaskPlan(
                id=task_ids[TaskCode.VALIDATION],
                task_code=TaskCode.VALIDATION,
                agent_type="VALIDATOR",
                objective="Validate evidence ownership, calculations, and policy citations.",
                depends_on=(
                    task_ids[TaskCode.CREDIT_ASSESSMENT],
                    task_ids[TaskCode.POLICY_CHECK],
                ),
            ),
            AnalysisTaskPlan(
                id=task_ids[TaskCode.SYNTHESIS],
                task_code=TaskCode.SYNTHESIS,
                agent_type="SYNTHESIZER",
                objective="Create a structured report draft after validation.",
                depends_on=(task_ids[TaskCode.VALIDATION],),
            ),
            AnalysisTaskPlan(
                id=task_ids[TaskCode.REPORT_GENERATION],
                task_code=TaskCode.REPORT_GENERATION,
                agent_type="REPORT",
                objective="Persist report JSON and request its PDF artifact.",
                depends_on=(task_ids[TaskCode.SYNTHESIS],),
            ),
        )
        return AnalysisPlan(analysis_case_id=analysis_case_id, tasks=tasks)

    async def run_experts(
        self,
        *,
        document_input: AgentInput,
        credit_input: AgentInput,
        compliance_input: AgentInput,
    ) -> tuple[AgentOutput, AgentOutput, AgentOutput]:
        """Use typed document readiness instead of treating every finding as a blocker."""

        document_output = await self._document.run(document_input)
        readiness = document_output.downstream_readiness
        credit_ready = (
            readiness.credit_context_ready
            if readiness is not None
            else not document_output.missing_information
        )
        compliance_ready = (
            readiness.compliance_context_ready
            if readiness is not None
            else not document_output.missing_information
        )
        blockers = readiness.blockers if readiness is not None else document_output.missing_information

        async def credit_result() -> AgentOutput:
            if not credit_ready:
                return _blocked_output(credit_input, self._credit.name.value, blockers)
            return await self._credit.run(credit_input)

        async def compliance_result() -> AgentOutput:
            if not compliance_ready:
                return _blocked_output(compliance_input, self._compliance.name.value, blockers)
            return await self._compliance.run(compliance_input)

        credit_output, compliance_output = await asyncio.gather(
            credit_result(), compliance_result()
        )
        return document_output, credit_output, compliance_output


def _blocked_output(
    request: AgentInput,
    name: str,
    blockers: tuple[str, ...] = ("document review completion",),
) -> AgentOutput:
    from decimal import Decimal

    from app.agents.base import AgentName

    return AgentOutput(
        agent_name=AgentName(name),
        task_id=request.task_id,
        conclusion="Task was not run because required document context is incomplete.",
        missing_information=blockers or ("document review completion",),
        limitations=("No expert analysis was executed.",),
        recommended_action="Complete document review and retry this task.",
        confidence=Decimal("0"),
    )
