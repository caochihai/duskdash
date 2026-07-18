from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.agents.base import (
    AgentName,
    AgentOutput,
    CalculationReference,
    EvidenceReference,
    FindingDraft,
    PolicyReference,
)
from app.agents.evaluation import (
    BoundedEvaluationCoordinator,
    EvaluationDimension,
    MockExpertEvaluationCoordinator,
    MockExpertEvaluator,
)


def _document_output(task_id: UUID, source_id: UUID) -> AgentOutput:
    evidence = EvidenceReference(
        source_type="DOCUMENT_VERSION",
        source_id=source_id,
        source_locator={"page": 1},
    )
    return AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=task_id,
        conclusion="Recorded document signals require authorized human review.",
        findings=(
            FindingDraft(
                finding_type="DOCUMENT_STATUS",
                title="Document was inspected",
                description="The recorded verification status is available.",
                severity="LOW",
                evidence=(evidence,),
            ),
        ),
        evidence_references=(evidence,),
        recommended_action="Continue authorized human document review.",
        confidence=Decimal("0.90"),
    )


def _credit_output(task_id: UUID, calculation_id: UUID) -> AgentOutput:
    calculation = CalculationReference(
        calculation_id=calculation_id,
        calculation_type="DTI",
        calculation_version="1",
        inputs={"accepted_income": "30000000", "monthly_debt": "12000000"},
        result_value=Decimal("0.4"),
        unit="RATIO",
    )
    return AgentOutput(
        agent_name=AgentName.CREDIT,
        task_id=task_id,
        conclusion="The persisted DTI was interpreted as decision support only.",
        findings=(
            FindingDraft(
                finding_type="REPAYMENT_INDICATOR",
                title="Persisted DTI is available",
                description="The calculation record contains the DTI result.",
                severity="LOW",
                calculation_ids=(calculation_id,),
            ),
        ),
        calculations=(calculation,),
        recommended_action="Submit the calculation to policy and human review.",
        confidence=Decimal("0.90"),
    )


def _compliance_output(task_id: UUID, clause_id: UUID) -> AgentOutput:
    policy = PolicyReference(
        policy_id=uuid4(),
        policy_version_id=uuid4(),
        clause_id=clause_id,
        clause_number="4.2",
        effective_date="2026-07-18",
    )
    return AgentOutput(
        agent_name=AgentName.LEGAL_COMPLIANCE,
        task_id=task_id,
        conclusion="The supplied approved policy clause was checked.",
        findings=(
            FindingDraft(
                finding_type="POLICY_CHECK",
                title="Policy condition requires review",
                description="The persisted policy check is conditional.",
                severity="MEDIUM",
                policy_clause_ids=(clause_id,),
            ),
        ),
        policy_references=(policy,),
        recommended_action="Ask an authorized reviewer to resolve the condition.",
        confidence=Decimal("0.90"),
    )


def test_mock_coordinator_accepts_cited_expert_outputs() -> None:
    source_id = uuid4()
    calculation_id = uuid4()
    clause_id = uuid4()
    outputs = (
        _document_output(uuid4(), source_id),
        _credit_output(uuid4(), calculation_id),
        _compliance_output(uuid4(), clause_id),
    )

    batch = asyncio.run(
        MockExpertEvaluationCoordinator().evaluate(
            outputs,
            frozenset({source_id}),
            frozenset({calculation_id}),
            frozenset({clause_id}),
        )
    )

    assert batch.approved
    assert batch.tasks_to_retry == ()
    assert batch.retry_rounds_used == 0
    assert batch.max_retry_rounds == 1
    assert all(evaluation.approved for evaluation in batch.final_evaluations)
    assert all(evaluation.feedback == () for evaluation in batch.final_evaluations)
    assert "does not prove factual correctness" in batch.limitations[0]


def test_mock_evaluator_reports_every_advisory_dimension() -> None:
    calculation_id = uuid4()
    clause_id = uuid4()
    unsafe_credit = AgentOutput(
        agent_name=AgentName.CREDIT,
        task_id=uuid4(),
        conclusion="The loan should be approved and this report is hallucination-free.",
        findings=(
            FindingDraft(
                finding_type="RISK",
                title="Unsupported claim",
                description="No source is attached.",
                severity="HIGH",
            ),
        ),
        calculations=(
            CalculationReference(
                calculation_id=calculation_id,
                calculation_type="DTI",
                inputs={"accepted_income": 1.2},
            ),
        ),
        policy_references=(
            PolicyReference(
                policy_id=uuid4(),
                policy_version_id=uuid4(),
                clause_id=clause_id,
                clause_number="X",
                effective_date="not-a-date",
            ),
        ),
        missing_information=("verified income",),
        contradictions=("declared income conflicts with salary evidence",),
        recommended_action="Continue processing.",
        confidence=Decimal("0.20"),
    )

    evaluation = MockExpertEvaluator().evaluate(
        unsafe_credit,
        authorized_source_ids=frozenset(),
        valid_calculation_ids=frozenset(),
        valid_policy_clause_ids=frozenset(),
    )

    dimensions = {issue.dimension for issue in evaluation.issues}
    assert dimensions == {
        EvaluationDimension.SCOPE,
        EvaluationDimension.CITATION,
        EvaluationDimension.CALCULATION,
        EvaluationDimension.POLICY,
        EvaluationDimension.MISSING_INFORMATION,
        EvaluationDimension.CONTRADICTION,
        EvaluationDimension.WRITING_SAFETY,
    }
    assert not evaluation.approved
    assert evaluation.retry_recommended
    assert evaluation.feedback


def test_mock_evaluator_rejects_document_authenticity_claim() -> None:
    output = AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=uuid4(),
        conclusion="The document is fake.",
        recommended_action="Continue processing.",
        confidence=Decimal("0.80"),
    )

    evaluation = MockExpertEvaluator().evaluate(output)

    assert any(issue.code == "DOCUMENT_AUTHENTICITY_CLAIM" for issue in evaluation.issues)


def test_mock_evaluator_allows_explicit_authenticity_limitation() -> None:
    output = AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=uuid4(),
        conclusion="Only recorded document presence signals were assessed.",
        limitations=(
            "The signals do not establish authenticity or prove that a document is genuine.",
        ),
        recommended_action="Request authorized human verification.",
        confidence=Decimal("0.80"),
    )

    evaluation = MockExpertEvaluator().evaluate(output)

    assert not any(
        issue.code == "DOCUMENT_AUTHENTICITY_CLAIM" for issue in evaluation.issues
    )


@pytest.mark.parametrize(
    "unsafe_language",
    (
        "Approve loan.",
        "Recommend approval of the loan.",
        "Khoản vay nên được phê duyệt.",
        "The loan should not be approved.",
    ),
)
def test_mock_evaluator_rejects_loan_decision_commands_and_recommendations(
    unsafe_language: str,
) -> None:
    output = AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=uuid4(),
        conclusion=unsafe_language,
        recommended_action="Authorized human review remains required.",
        confidence=Decimal("0.80"),
    )

    evaluation = MockExpertEvaluator().evaluate(output)

    assert any(
        issue.code == "AUTOMATED_LOAN_DECISION_LANGUAGE"
        for issue in evaluation.issues
    )


@pytest.mark.parametrize(
    "safe_language",
    (
        "This analysis does not recommend approval of the loan.",
        "This report does not approve or reject the loan.",
        "Báo cáo này không khuyến nghị phê duyệt khoản vay.",
    ),
)
def test_mock_evaluator_allows_explicit_loan_decision_disclaimers(
    safe_language: str,
) -> None:
    output = AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=uuid4(),
        conclusion=safe_language,
        recommended_action="Request an authorized human decision.",
        confidence=Decimal("0.80"),
    )

    evaluation = MockExpertEvaluator().evaluate(output)

    assert not any(
        issue.code == "AUTOMATED_LOAN_DECISION_LANGUAGE"
        for issue in evaluation.issues
    )


def test_authenticity_negation_in_another_clause_does_not_hide_claim() -> None:
    output = AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=uuid4(),
        conclusion="Document does not contain errors, and document is genuine.",
        recommended_action="Request authorized human verification.",
        confidence=Decimal("0.80"),
    )

    evaluation = MockExpertEvaluator().evaluate(output)

    assert any(issue.code == "DOCUMENT_AUTHENTICITY_CLAIM" for issue in evaluation.issues)


def test_bounded_coordinator_never_retries_more_than_once() -> None:
    output = AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=uuid4(),
        conclusion="The document is fake.",
        recommended_action="Continue processing.",
        confidence=Decimal("0.80"),
    )
    attempts: list[UUID] = []

    async def unchanged_retry(
        current: AgentOutput, evaluation: object
    ) -> AgentOutput:
        assert evaluation is not None
        attempts.append(current.task_id)
        return current

    final_outputs, batch = asyncio.run(
        BoundedEvaluationCoordinator().run((output,), retry_callback=unchanged_retry)
    )

    assert final_outputs == (output,)
    assert attempts == [output.task_id]
    assert batch.retry_rounds_used == 1
    assert batch.retry_limit_reached
    assert batch.tasks_to_retry == (output.task_id,)
    assert batch.final_evaluations[0].feedback_round == 1


def test_bounded_coordinator_accepts_safe_feedback_replacement() -> None:
    output = AgentOutput(
        agent_name=AgentName.DOCUMENT,
        task_id=uuid4(),
        conclusion="The document is fake.",
        recommended_action="Continue processing.",
        confidence=Decimal("0.80"),
    )

    async def safe_retry(current: AgentOutput, evaluation: object) -> AgentOutput:
        assert evaluation is not None
        return current.model_copy(
            update={
                "conclusion": "A recorded verification signal requires human review.",
                "recommended_action": "Request authorized human verification.",
            }
        )

    final_outputs, batch = asyncio.run(
        BoundedEvaluationCoordinator().run((output,), retry_callback=safe_retry)
    )

    assert final_outputs[0].task_id == output.task_id
    assert batch.approved
    assert batch.tasks_to_retry == ()
    assert batch.retry_attempted_task_ids == (output.task_id,)
    assert batch.retry_rounds_used == 1
    assert not batch.retry_limit_reached
