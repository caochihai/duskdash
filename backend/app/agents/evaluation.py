"""Bounded design-time feedback for structured expert outputs.

This module deliberately complements, rather than replaces, ``EvidenceValidator``.
The evaluator only applies deterministic shape, scope, citation, and writing-safety
heuristics to an ``AgentOutput``.  It cannot establish source ownership, prove that
a claim is true, or guarantee the absence of hallucinations.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from datetime import date
from app.compat import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import AgentName, AgentOutput, FindingDraft


class _EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationDimension(StrEnum):
    SCOPE = "SCOPE"
    CITATION = "CITATION"
    CALCULATION = "CALCULATION"
    POLICY = "POLICY"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    CONTRADICTION = "CONTRADICTION"
    WRITING_SAFETY = "WRITING_SAFETY"


class EvaluationSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class EvaluationIssue(_EvaluationModel):
    """One deterministic, actionable issue found in an expert output."""

    dimension: EvaluationDimension
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    severity: EvaluationSeverity = EvaluationSeverity.ERROR


class ExpertEvaluation(_EvaluationModel):
    """Evaluation of one expert output in one bounded feedback round."""

    agent_name: AgentName
    task_id: UUID
    feedback_round: int = Field(ge=0, le=1)
    approved: bool
    issues: tuple[EvaluationIssue, ...] = ()
    feedback: tuple[str, ...] = ()
    retry_recommended: bool
    evaluator: Literal["MOCK_DETERMINISTIC"] = "MOCK_DETERMINISTIC"


class EvaluationBatch(_EvaluationModel):
    """Auditable result of initial evaluation and at most one feedback round."""

    initial_evaluations: tuple[ExpertEvaluation, ...]
    final_evaluations: tuple[ExpertEvaluation, ...]
    tasks_to_retry: tuple[UUID, ...] = ()
    retry_attempted_task_ids: tuple[UUID, ...] = ()
    recommendations: tuple[str, ...] = ()
    retry_rounds_used: int = Field(ge=0, le=1)
    max_retry_rounds: Literal[1] = 1
    approved: bool
    retry_limit_reached: bool = False
    limitations: tuple[str, ...] = (
        "Mock deterministic evaluation does not prove factual correctness or guarantee the absence "
        "of hallucinations; EvidenceValidator and authorized human review remain required.",
    )


_DECISION_PATTERNS = (
    re.compile(
        r"\b(?:loan|loan application|application)\s+"
        r"(?:is|has been|(?:should|must)(?:\s+not)?\s+be)\s+"
        r"(?:approved|rejected)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:approve|reject)\s+(?:(?:this|the)\s+)?"
        r"(?:loan|loan application|application)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brecommend(?:s|ed|ing)?\s+(?:the\s+)?(?:approval|rejection)\s+of\s+"
        r"(?:(?:this|the)\s+)?(?:loan|loan application|application)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brecommend(?:s|ed|ing)?\s+(?:approving|rejecting)\s+"
        r"(?:(?:this|the)\s+)?(?:loan|loan application|application)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:phê duyệt|từ chối)\s+(?:khoản vay|hồ sơ vay|đơn vay)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:khuyến nghị|đề nghị)\s+(?:nên\s+)?(?:phê duyệt|từ chối)\s+"
        r"(?:khoản vay|hồ sơ vay|đơn vay)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:khoản vay|hồ sơ vay|đơn vay)(?:\s+này)?\s+"
        r"(?:(?:nên|phải|cần|không nên)\s+(?:được\s+)?|không được\s+)"
        r"(?:phê duyệt|từ chối)\b",
        re.IGNORECASE,
    ),
)
_AUTHENTICITY_PATTERNS = (
    re.compile(
        r"\b(?:document|signature|seal|stamp)\s+(?:is|has been)\s+"
        r"(?:(?:not\s+)?(?:genuine|authentic)|fake|forged|fraudulent)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:hồ sơ|tài liệu|chữ ký|con dấu|dấu đỏ)\s+(?:là\s+)?"
        r"(?:thật|giả|giả mạo)\b",
        re.IGNORECASE,
    ),
)
_ASSURANCE_PATTERNS = (
    re.compile(r"\bhallucination[- ]free\b", re.IGNORECASE),
    re.compile(r"\bguarantees?\s+(?:zero|no)\s+hallucinations?\b", re.IGNORECASE),
    re.compile(r"\b(?:legally valid|complies with all laws)\b", re.IGNORECASE),
)
_DECISION_DISCLAIMER_PATTERNS = (
    re.compile(
        r"\b(?:this\s+|the\s+)?(?:analysis|report|output|agent|model|system|ai)\s+"
        r"(?:(?:does|do|will)\s+not|cannot|can't)\s+"
        r"(?:automatically\s+)?(?:approve|reject|recommend)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:please\s+)?(?:do\s+not|never)\s+(?:automatically\s+)?"
        r"(?:approve|reject|recommend)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:báo cáo|phân tích|đầu ra|agent|mô hình|hệ thống|ai)(?:\s+này)?\s+"
        r"(?:không|không thể|chưa thể)\s+(?:tự động\s+)?"
        r"(?:phê duyệt|từ chối|khuyến nghị|đề nghị)\b",
        re.IGNORECASE,
    ),
)
_AUTHENTICITY_LIMITATION_PATTERNS = (
    re.compile(
        r"\b(?:does?|do|did|will|would|can|could)\s+not\s+"
        r"(?:establish|prove|determine|verify|confirm|guarantee)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:cannot|can't|couldn't)\s+"
        r"(?:establish|prove|determine|verify|confirm|guarantee)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwithout\s+(?:establishing|proving|determining|verifying|confirming)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:không|không thể|chưa thể)\s+"
        r"(?:xác minh|kết luận|chứng minh|khẳng định)\b",
        re.IGNORECASE,
    ),
)


class MockExpertEvaluator:
    """Deterministic evaluator for design and tests, never a truth oracle."""

    def evaluate(
        self,
        output: AgentOutput,
        *,
        feedback_round: int = 0,
        authorized_source_ids: frozenset[UUID] | None = None,
        valid_calculation_ids: frozenset[UUID] | None = None,
        valid_policy_clause_ids: frozenset[UUID] | None = None,
    ) -> ExpertEvaluation:
        if feedback_round not in {0, 1}:
            raise ValueError("feedback_round must be 0 or 1")

        issues: list[EvaluationIssue] = []
        self._evaluate_scope(output, issues)
        self._evaluate_citations(output, issues)
        self._evaluate_calculations(output, issues)
        self._evaluate_policy(output, issues)
        self._evaluate_reference_scope(
            output,
            issues,
            authorized_source_ids=authorized_source_ids,
            valid_calculation_ids=valid_calculation_ids,
            valid_policy_clause_ids=valid_policy_clause_ids,
        )
        self._evaluate_completeness(output, issues)
        self._evaluate_writing_safety(output, issues)

        feedback = _unique(issue.recommendation for issue in issues)
        approved = not any(issue.severity == EvaluationSeverity.ERROR for issue in issues)
        return ExpertEvaluation(
            agent_name=output.agent_name,
            task_id=output.task_id,
            feedback_round=feedback_round,
            approved=approved,
            issues=tuple(issues),
            feedback=feedback,
            retry_recommended=not approved,
        )

    def evaluate_many(
        self,
        outputs: Sequence[AgentOutput],
        *,
        feedback_round: int = 0,
        authorized_source_ids: frozenset[UUID] | None = None,
        valid_calculation_ids: frozenset[UUID] | None = None,
        valid_policy_clause_ids: frozenset[UUID] | None = None,
    ) -> tuple[ExpertEvaluation, ...]:
        return tuple(
            self.evaluate(
                output,
                feedback_round=feedback_round,
                authorized_source_ids=authorized_source_ids,
                valid_calculation_ids=valid_calculation_ids,
                valid_policy_clause_ids=valid_policy_clause_ids,
            )
            for output in outputs
        )

    @staticmethod
    def _evaluate_scope(output: AgentOutput, issues: list[EvaluationIssue]) -> None:
        if output.agent_name == AgentName.DOCUMENT:
            if output.calculations:
                _add_issue(
                    issues,
                    EvaluationDimension.SCOPE,
                    "DOCUMENT_CALCULATION_OUT_OF_SCOPE",
                    "Document Agent output contains financial calculations.",
                    "Move deterministic financial calculations to CalculationService and Credit Agent.",
                )
            if output.policy_references:
                _add_issue(
                    issues,
                    EvaluationDimension.SCOPE,
                    "DOCUMENT_POLICY_OUT_OF_SCOPE",
                    "Document Agent output applies policy references.",
                    "Move policy interpretation to Legal/Compliance Agent.",
                )
        elif output.agent_name == AgentName.CREDIT and output.policy_references:
            _add_issue(
                issues,
                EvaluationDimension.SCOPE,
                "CREDIT_POLICY_OUT_OF_SCOPE",
                "Credit Agent output contains policy references or thresholds.",
                "Let Credit Agent interpret calculations and let Legal/Compliance Agent apply policy.",
            )
        elif output.agent_name == AgentName.LEGAL_COMPLIANCE and output.calculations:
            _add_issue(
                issues,
                EvaluationDimension.SCOPE,
                "COMPLIANCE_CALCULATION_OUT_OF_SCOPE",
                "Legal/Compliance Agent output contains financial calculations.",
                "Use persisted CalculationService results through Credit Agent.",
            )

    @staticmethod
    def _evaluate_citations(output: AgentOutput, issues: list[EvaluationIssue]) -> None:
        declared_evidence = {
            (reference.source_type, reference.source_id) for reference in output.evidence_references
        }
        declared_calculations = {
            calculation.calculation_id for calculation in output.calculations
        }
        declared_clauses = {policy.clause_id for policy in output.policy_references}

        for finding in output.findings:
            if not (
                finding.evidence or finding.calculation_ids or finding.policy_clause_ids
            ):
                _add_issue(
                    issues,
                    EvaluationDimension.CITATION,
                    "UNCITED_FINDING",
                    f"Finding '{finding.title}' has no evidence, calculation, or policy citation.",
                    "Attach persisted source, calculation, or effective policy references to the finding.",
                )

            undeclared_evidence = tuple(
                reference.source_id
                for reference in finding.evidence
                if (reference.source_type, reference.source_id) not in declared_evidence
            )
            if undeclared_evidence:
                _add_issue(
                    issues,
                    EvaluationDimension.CITATION,
                    "UNDECLARED_EVIDENCE_REFERENCE",
                    f"Finding '{finding.title}' cites evidence absent from evidence_references.",
                    "Declare every finding evidence reference in the expert output.",
                )
            if any(
                calculation_id not in declared_calculations
                for calculation_id in finding.calculation_ids
            ):
                _add_issue(
                    issues,
                    EvaluationDimension.CITATION,
                    "UNDECLARED_CALCULATION_REFERENCE",
                    f"Finding '{finding.title}' cites an undeclared calculation.",
                    "Use only persisted calculation IDs declared in the expert output.",
                )
            if any(
                clause_id not in declared_clauses for clause_id in finding.policy_clause_ids
            ):
                _add_issue(
                    issues,
                    EvaluationDimension.CITATION,
                    "UNDECLARED_POLICY_REFERENCE",
                    f"Finding '{finding.title}' cites an undeclared policy clause.",
                    "Attach the approved effective policy reference for every cited clause.",
                )

    @staticmethod
    def _evaluate_calculations(output: AgentOutput, issues: list[EvaluationIssue]) -> None:
        if output.agent_name == AgentName.CREDIT and not output.calculations:
            _add_issue(
                issues,
                EvaluationDimension.CALCULATION,
                "MISSING_CALCULATION_REFERENCE",
                "Credit Agent output has no persisted deterministic calculation reference.",
                "Run CalculationService and cite its persisted calculation records.",
            )

        for calculation in output.calculations:
            if calculation.result_value is None and not calculation.result_payload:
                _add_issue(
                    issues,
                    EvaluationDimension.CALCULATION,
                    "EMPTY_CALCULATION_RESULT",
                    f"Calculation {calculation.calculation_id} has no persisted result.",
                    "Persist a Decimal result or structured result payload before expert interpretation.",
                )
            if _contains_binary_float(calculation.inputs) or _contains_binary_float(
                calculation.result_payload
            ):
                _add_issue(
                    issues,
                    EvaluationDimension.CALCULATION,
                    "BINARY_FLOAT_IN_FINANCIAL_DATA",
                    f"Calculation {calculation.calculation_id} contains a binary float.",
                    "Use Decimal-compatible string or Decimal values for financial data.",
                )

    @staticmethod
    def _evaluate_policy(output: AgentOutput, issues: list[EvaluationIssue]) -> None:
        if output.agent_name == AgentName.LEGAL_COMPLIANCE and not output.policy_references:
            _add_issue(
                issues,
                EvaluationDimension.POLICY,
                "MISSING_POLICY_REFERENCE",
                "Legal/Compliance Agent output has no approved effective policy reference.",
                "Supply an approved policy version and clause effective for the assessment date.",
            )

        for policy in output.policy_references:
            try:
                date.fromisoformat(policy.effective_date)
            except ValueError:
                _add_issue(
                    issues,
                    EvaluationDimension.POLICY,
                    "INVALID_POLICY_EFFECTIVE_DATE",
                    f"Policy clause {policy.clause_id} has an invalid effective date.",
                    "Use the persisted ISO policy effective date.",
                )

        if output.agent_name == AgentName.LEGAL_COMPLIANCE:
            for finding in output.findings:
                if finding.finding_type == "POLICY_CHECK" and not finding.policy_clause_ids:
                    _add_issue(
                        issues,
                        EvaluationDimension.POLICY,
                        "UNCITED_POLICY_FINDING",
                        f"Policy finding '{finding.title}' has no clause citation.",
                        "Cite the approved policy version and exact clause used by the check.",
                    )

    @staticmethod
    def _evaluate_reference_scope(
        output: AgentOutput,
        issues: list[EvaluationIssue],
        *,
        authorized_source_ids: frozenset[UUID] | None,
        valid_calculation_ids: frozenset[UUID] | None,
        valid_policy_clause_ids: frozenset[UUID] | None,
    ) -> None:
        evidence = tuple(output.evidence_references) + tuple(
            reference for finding in output.findings for reference in finding.evidence
        )
        if authorized_source_ids is not None and any(
            reference.source_id not in authorized_source_ids for reference in evidence
        ):
            _add_issue(
                issues,
                EvaluationDimension.CITATION,
                "EVIDENCE_OUTSIDE_EVALUATION_SCOPE",
                "Expert output references evidence outside the supplied evaluation scope.",
                "Remove the reference and reload evidence through the authorized case context.",
            )

        calculation_ids = tuple(
            calculation.calculation_id for calculation in output.calculations
        ) + tuple(
            calculation_id
            for finding in output.findings
            for calculation_id in finding.calculation_ids
        )
        if valid_calculation_ids is not None and any(
            calculation_id not in valid_calculation_ids for calculation_id in calculation_ids
        ):
            _add_issue(
                issues,
                EvaluationDimension.CALCULATION,
                "CALCULATION_OUTSIDE_EVALUATION_SCOPE",
                "Expert output references a calculation outside the supplied valid set.",
                "Use a persisted calculation owned by the current analysis case.",
            )

        policy_clause_ids = tuple(
            policy.clause_id for policy in output.policy_references
        ) + tuple(
            clause_id
            for finding in output.findings
            for clause_id in finding.policy_clause_ids
        )
        if valid_policy_clause_ids is not None and any(
            clause_id not in valid_policy_clause_ids for clause_id in policy_clause_ids
        ):
            _add_issue(
                issues,
                EvaluationDimension.POLICY,
                "POLICY_OUTSIDE_EVALUATION_SCOPE",
                "Expert output references a policy clause outside the supplied valid set.",
                "Use an approved clause from the effective policy version for this analysis.",
            )

    @staticmethod
    def _evaluate_completeness(output: AgentOutput, issues: list[EvaluationIssue]) -> None:
        for item in output.missing_information:
            _add_issue(
                issues,
                EvaluationDimension.MISSING_INFORMATION,
                "MISSING_REQUIRED_INFORMATION",
                f"{output.agent_name.value} reports missing information: {item}",
                "Collect or verify the missing information, or keep the result explicitly incomplete.",
            )
        for item in output.contradictions:
            _add_issue(
                issues,
                EvaluationDimension.CONTRADICTION,
                "UNRESOLVED_CONTRADICTION",
                f"{output.agent_name.value} reports an unresolved contradiction: {item}",
                "Resolve the cited contradiction through an authorized source or human review.",
            )

    @staticmethod
    def _evaluate_writing_safety(output: AgentOutput, issues: list[EvaluationIssue]) -> None:
        text = _output_text(output)
        if _has_unqualified_decision_match(text):
            _add_issue(
                issues,
                EvaluationDimension.WRITING_SAFETY,
                "AUTOMATED_LOAN_DECISION_LANGUAGE",
                "Expert output contains approval or rejection decision language.",
                "Use decision-support language and leave the official decision to an authorized human.",
            )
        if _has_unqualified_match(text, _AUTHENTICITY_PATTERNS):
            _add_issue(
                issues,
                EvaluationDimension.WRITING_SAFETY,
                "DOCUMENT_AUTHENTICITY_CLAIM",
                "Expert output makes a definitive authenticity or fraud claim.",
                "Report recorded presence or verification signals and require qualified human review.",
            )
        if any(pattern.search(text) for pattern in _ASSURANCE_PATTERNS):
            _add_issue(
                issues,
                EvaluationDimension.WRITING_SAFETY,
                "ABSOLUTE_ASSURANCE_CLAIM",
                "Expert output makes an unsupported absolute assurance claim.",
                "State the evidence, uncertainty, limitations, and need for authorized human review.",
            )


class BoundedEvaluationCoordinator:
    """Evaluate expert outputs and optionally execute exactly one feedback round."""

    max_retry_rounds: Literal[1] = 1

    def __init__(self, evaluator: MockExpertEvaluator | None = None) -> None:
        self._evaluator = evaluator or MockExpertEvaluator()

    async def run(
        self,
        outputs: tuple[AgentOutput, ...],
        *,
        authorized_source_ids: frozenset[UUID] | None = None,
        valid_calculation_ids: frozenset[UUID] | None = None,
        valid_policy_clause_ids: frozenset[UUID] | None = None,
        retry_callback: Callable[[AgentOutput, ExpertEvaluation], Awaitable[AgentOutput]] | None = None,
    ) -> tuple[tuple[AgentOutput, ...], EvaluationBatch]:
        _ensure_unique_task_ids(outputs)
        initial = self._evaluator.evaluate_many(
            outputs,
            feedback_round=0,
            authorized_source_ids=authorized_source_ids,
            valid_calculation_ids=valid_calculation_ids,
            valid_policy_clause_ids=valid_policy_clause_ids,
        )
        candidates = tuple(item for item in initial if item.retry_recommended)

        if retry_callback is None or not candidates:
            batch = _batch(
                initial=initial,
                final=initial,
                retry_attempted_task_ids=(),
                retry_rounds_used=0,
                retry_limit_reached=False,
            )
            return outputs, batch

        evaluation_by_task = {item.task_id: item for item in candidates}
        retried_outputs: list[AgentOutput] = []
        attempted: list[UUID] = []
        for output in outputs:
            evaluation = evaluation_by_task.get(output.task_id)
            if evaluation is None:
                retried_outputs.append(output)
                continue
            replacement = await retry_callback(output, evaluation)
            if replacement.task_id != output.task_id:
                raise ValueError("retry callback must preserve task_id")
            if replacement.agent_name != output.agent_name:
                raise ValueError("retry callback must preserve agent_name")
            retried_outputs.append(replacement)
            attempted.append(output.task_id)

        final_outputs = tuple(retried_outputs)
        retry_evaluations = {
            output.task_id: self._evaluator.evaluate(
                output,
                feedback_round=1,
                authorized_source_ids=authorized_source_ids,
                valid_calculation_ids=valid_calculation_ids,
                valid_policy_clause_ids=valid_policy_clause_ids,
            )
            for output in final_outputs
            if output.task_id in evaluation_by_task
        }
        final = tuple(retry_evaluations.get(item.task_id, item) for item in initial)
        remaining = any(item.retry_recommended for item in final)
        batch = _batch(
            initial=initial,
            final=final,
            retry_attempted_task_ids=tuple(attempted),
            retry_rounds_used=1,
            retry_limit_reached=remaining,
        )
        return final_outputs, batch


class MockExpertEvaluationCoordinator(BoundedEvaluationCoordinator):
    """Simple simulation facade returning advisory evaluation metadata only."""

    async def evaluate(
        self,
        outputs: tuple[AgentOutput, ...],
        authorized_source_ids: frozenset[UUID],
        valid_calculation_ids: frozenset[UUID],
        valid_policy_clause_ids: frozenset[UUID],
    ) -> EvaluationBatch:
        _, batch = await self.run(
            outputs,
            authorized_source_ids=authorized_source_ids,
            valid_calculation_ids=valid_calculation_ids,
            valid_policy_clause_ids=valid_policy_clause_ids,
        )
        return batch


def _batch(
    *,
    initial: tuple[ExpertEvaluation, ...],
    final: tuple[ExpertEvaluation, ...],
    retry_attempted_task_ids: tuple[UUID, ...],
    retry_rounds_used: int,
    retry_limit_reached: bool,
) -> EvaluationBatch:
    retry = tuple(item.task_id for item in final if item.retry_recommended)
    recommendations = _unique(
        recommendation
        for evaluation in final
        for recommendation in evaluation.feedback
    )
    return EvaluationBatch(
        initial_evaluations=initial,
        final_evaluations=final,
        tasks_to_retry=retry,
        retry_attempted_task_ids=retry_attempted_task_ids,
        recommendations=recommendations,
        retry_rounds_used=retry_rounds_used,
        approved=not retry,
        retry_limit_reached=retry_limit_reached,
    )


def _add_issue(
    issues: list[EvaluationIssue],
    dimension: EvaluationDimension,
    code: str,
    message: str,
    recommendation: str,
) -> None:
    candidate = EvaluationIssue(
        dimension=dimension,
        code=code,
        message=message,
        recommendation=recommendation,
    )
    key = (candidate.dimension, candidate.code, candidate.message)
    if any((item.dimension, item.code, item.message) == key for item in issues):
        return
    issues.append(candidate)


def _output_text(output: AgentOutput) -> str:
    values: list[str] = [output.conclusion, output.recommended_action]
    values.extend(output.assumptions)
    values.extend(output.missing_information)
    values.extend(output.contradictions)
    values.extend(output.risk_flags)
    values.extend(output.limitations)
    for finding in output.findings:
        values.extend(_finding_text(finding))
    return "\n".join(values)


def _has_unqualified_match(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    """Ignore authenticity only when its local clause denies verification certainty."""

    for pattern in patterns:
        for match in pattern.finditer(text):
            fragment = _local_clause_fragment(text, match.start(), match.end())
            if not any(
                qualifier.search(fragment)
                for qualifier in _AUTHENTICITY_LIMITATION_PATTERNS
            ):
                return True
    return False


def _has_unqualified_decision_match(text: str) -> bool:
    for pattern in _DECISION_PATTERNS:
        for match in pattern.finditer(text):
            fragment = _local_clause_fragment(text, match.start(), match.end())
            if not any(pattern.search(fragment) for pattern in _DECISION_DISCLAIMER_PATTERNS):
                return True
    return False


def _local_clause_fragment(text: str, match_start: int, match_end: int) -> str:
    """Return text local to a match, respecting punctuation and conjunction boundaries."""

    prefix = text[:match_start]
    starts = [prefix.rfind(mark) + 1 for mark in (".", "!", "?", ";", "\n")]
    for boundary in re.finditer(r",\s*(?:and|but|và|nhưng)\s+", prefix, re.IGNORECASE):
        starts.append(boundary.end())
    return text[max(starts) : match_end]


def _finding_text(finding: FindingDraft) -> tuple[str, ...]:
    return tuple(
        value
        for value in (
            finding.finding_type,
            finding.title,
            finding.description,
            finding.recommended_action,
        )
        if value is not None
    )


def _contains_binary_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, Mapping):
        return any(_contains_binary_float(item) for item in value.values())
    if isinstance(value, (str, bytes, bytearray)):
        return False
    if isinstance(value, Iterable):
        return any(_contains_binary_float(item) for item in value)
    return False


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _ensure_unique_task_ids(outputs: tuple[AgentOutput, ...]) -> None:
    task_ids = [output.task_id for output in outputs]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("expert outputs must have unique task_id values")
