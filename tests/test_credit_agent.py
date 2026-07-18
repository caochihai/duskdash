from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from decimal import Decimal
from typing import Any

from credit_agent.agent import CreditAgent
from credit_agent.models import (
    CreditAnalysisResultV1,
    CreditPolicyData,
    Decision,
    RiskCode,
    ResultStatus,
)


EXPECTED_TOOL_NAMES = {
    "retrieve_credit_policy",
    "get_customer_360",
    "get_credit_facilities",
    "get_repayment_history",
    "get_transaction_summary",
    "get_financial_statements",
    "calculate_financial_metrics",
    "get_collateral_snapshot",
}
NON_POSITIVE_DECISIONS = {
    Decision.NEEDS_INFO,
    Decision.MANUAL_REVIEW,
    Decision.NOT_RECOMMENDED,
    Decision.SYSTEM_EXCEPTION,
}


def run_credit_agent(case: Any, task: Any | None = None) -> CreditAnalysisResultV1:
    """Exercise the public async API from ordinary synchronous pytest tests."""

    return asyncio.run(CreditAgent(tools=case.tools).run(task or case.task))


def _all_evidence_links(result: CreditAnalysisResultV1) -> Iterable[str]:
    yield from result.recommendation.evidence_ids
    for analysis in (
        result.relationship_analysis,
        result.facility_analysis,
        result.repayment_analysis,
        result.cashflow_analysis,
        result.collateral_analysis,
    ):
        if analysis is not None:
            yield from analysis.evidence_ids
    for item in result.risk_flags:
        yield from item.evidence_ids
    for item in result.conditions:
        yield from item.evidence_ids
    for item in result.follow_up_questions:
        yield from item.evidence_ids
    for item in result.data_quality.conflicts:
        yield from item.evidence_ids
    for item in result.next_actions:
        yield from item.evidence_ids
    for item in result.info_requests:
        yield from item.evidence_ids


def assert_public_result_invariants(result: CreditAnalysisResultV1) -> None:
    assert len(result.follow_up_questions) <= 5

    evidence_ids = [item.evidence_id for item in result.evidence]
    assert len(evidence_ids) == len(set(evidence_ids))
    assert set(_all_evidence_links(result)) <= set(evidence_ids)

    claim_ids = {item.claim_id for item in result.evidence}
    assert all(set(citation.claim_ids) <= claim_ids for citation in result.policy_citations)

    if result.recommendation.decision in NON_POSITIVE_DECISIONS:
        assert result.recommendation.recommended_limit is None
        assert result.recommendation.recommended_tenor_months is None
        assert result.recommendation.currency is None


def test_happy_path_is_ready_and_uses_all_eight_tools(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()

    result = run_credit_agent(case)

    assert result.status == ResultStatus.COMPLETED
    assert result.recommendation.decision == Decision.READY_FOR_APPROVAL_REVIEW
    assert result.recommendation.recommended_limit == Decimal("1000000")
    assert result.recommendation.recommended_tenor_months == 12
    assert result.recommendation.human_approval_required is True
    assert result.missing_information == []
    assert result.errors == []
    assert result.tool_call_count == 8
    assert len(case.tools.calls) == 8
    assert set(case.tools.calls) == EXPECTED_TOOL_NAMES
    assert_public_result_invariants(result)


def test_invalid_zero_limit_returns_needs_info_without_tool_calls(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    invalid_task = case.task.model_dump(mode="json")
    invalid_task["credit_request"]["requested_limit"] = 0

    result = run_credit_agent(case, invalid_task)

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert result.tool_call_count == 0
    assert case.tools.calls == []
    assert any("requested_limit" in item for item in result.missing_information)
    assert_public_result_invariants(result)


def test_mandatory_tool_error_is_system_exception_with_failed_tool_name(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.set_tool_error("get_repayment_history", "loan ledger unavailable")

    result = run_credit_agent(case)

    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.recommendation.decision == Decision.SYSTEM_EXCEPTION
    assert len(result.errors) == 1
    assert result.errors[0].code == "MANDATORY_TOOL_FAILED"
    assert result.errors[0].tool_name == "get_repayment_history"
    assert "get_repayment_history" in case.tools.calls
    assert "calculate_financial_metrics" not in case.tools.calls
    assert_public_result_invariants(result)


def test_missing_prior_statement_needs_info_and_skips_calculator(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data("get_financial_statements", prior=None)
    case.tools.fail_if_called.add("calculate_financial_metrics")

    result = run_credit_agent(case)

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert "prior-period financial statement" in result.missing_information
    assert "deterministic financial metrics" in result.missing_information
    assert "calculate_financial_metrics" not in case.tools.calls
    assert result.tool_call_count == 7
    assert_public_result_invariants(result)


def test_material_outstanding_conflict_routes_to_manual_review(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data("get_customer_360", total_outstanding=Decimal("500000"))

    result = run_credit_agent(case)

    assert result.status == ResultStatus.COMPLETED
    assert result.recommendation.decision == Decision.MANUAL_REVIEW
    assert result.data_quality.conflicts_detected == 1
    assert {
        conflict.conflict_code for conflict in result.data_quality.conflicts
    } == {"OUTSTANDING_BALANCE_CONFLICT"}
    assert RiskCode.FINANCIAL_DATA_CONFLICT in {flag.code for flag in result.risk_flags}
    assert any(question.blocking_if_unanswered for question in result.follow_up_questions)
    assert_public_result_invariants(result)


def test_related_party_flow_routes_to_manual_review_and_compliance_info_request(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data("get_transaction_summary", related_party_flow=True)

    result = run_credit_agent(case)

    assert result.status == ResultStatus.COMPLETED
    assert result.recommendation.decision == Decision.MANUAL_REVIEW
    assert RiskCode.RELATED_PARTY_FLOW in {flag.code for flag in result.risk_flags}
    assert len(result.info_requests) == 1
    assert result.info_requests[0].message_type == "INFO_REQUEST"
    assert result.info_requests[0].target_agent == "compliance_agent"
    assert_public_result_invariants(result)


def test_low_utilization_decision_changes_only_when_policy_threshold_crosses_value(
    credit_case_factory: Callable[[], Any],
) -> None:
    below_threshold_case = credit_case_factory()
    below_facilities = below_threshold_case.tools.outputs["get_credit_facilities"].data
    assert below_facilities is not None
    below_record = below_facilities.facilities[0].model_copy(
        update={"outstanding": Decimal("450000"), "utilization_ratio": Decimal("0.45")}
    )
    below_threshold_case.tools.update_data(
        "get_credit_facilities",
        outstanding=Decimal("450000"),
        utilization_ratio=Decimal("0.45"),
        facilities=[below_record],
    )
    below_threshold_case.tools.update_data(
        "get_customer_360", total_outstanding=Decimal("450000")
    )
    below_threshold_case.tools.update_policy_thresholds(
        low_limit_utilization_threshold=Decimal("0.40")
    )

    above_threshold_case = credit_case_factory()
    above_facilities = above_threshold_case.tools.outputs["get_credit_facilities"].data
    assert above_facilities is not None
    above_record = above_facilities.facilities[0].model_copy(
        update={"outstanding": Decimal("450000"), "utilization_ratio": Decimal("0.45")}
    )
    above_threshold_case.tools.update_data(
        "get_credit_facilities",
        outstanding=Decimal("450000"),
        utilization_ratio=Decimal("0.45"),
        facilities=[above_record],
    )
    above_threshold_case.tools.update_data(
        "get_customer_360", total_outstanding=Decimal("450000")
    )
    above_threshold_case.tools.update_policy_thresholds(
        low_limit_utilization_threshold=Decimal("0.50")
    )

    ready = run_credit_agent(below_threshold_case)
    conditional = run_credit_agent(above_threshold_case)

    assert ready.recommendation.decision == Decision.READY_FOR_APPROVAL_REVIEW
    assert conditional.recommendation.decision == Decision.PASS_WITH_CONDITIONS
    assert RiskCode.LOW_LIMIT_UTILIZATION not in {flag.code for flag in ready.risk_flags}
    assert RiskCode.LOW_LIMIT_UTILIZATION in {
        flag.code for flag in conditional.risk_flags
    }
    assert {condition.condition_code for condition in conditional.conditions} == {
        "RESOLVE_LOW_LIMIT_UTILIZATION"
    }
    assert_public_result_invariants(ready)
    assert_public_result_invariants(conditional)


def test_follow_up_questions_are_capped_at_five_and_all_are_grounded(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()

    metrics_envelope = case.tools.outputs["calculate_financial_metrics"]
    metrics_data = metrics_envelope.data
    assert metrics_data is not None
    metrics = dict(metrics_data.metrics)
    for name, value in {
        "revenue_transaction_variance_ratio": "0.40",
        "receivables_growth": "0.50",
        "inventory_growth": "0.50",
    }.items():
        metrics[name] = metrics[name].model_copy(update={"current": Decimal(value)})
    case.tools.outputs["calculate_financial_metrics"] = metrics_envelope.model_copy(
        update={"data": metrics_data.model_copy(update={"metrics": metrics})}
    )

    statements_envelope = case.tools.outputs["get_financial_statements"]
    statements_data = statements_envelope.data
    assert statements_data is not None and statements_data.current is not None
    case.tools.update_data(
        "get_financial_statements",
        current=statements_data.current.model_copy(
            update={"operating_cash_flow": Decimal("-100000")}
        ),
    )
    case.tools.update_data(
        "get_repayment_history",
        late_payment_count=2,
        max_days_past_due=30,
        restructured_debt=True,
    )
    facilities = case.tools.outputs["get_credit_facilities"].data
    assert facilities is not None
    case.tools.update_data(
        "get_credit_facilities",
        outstanding=Decimal("200000"),
        utilization_ratio=Decimal("0.20"),
        facilities=[
            facilities.facilities[0].model_copy(
                update={"outstanding": Decimal("200000"), "utilization_ratio": Decimal("0.20")}
            )
        ],
    )
    case.tools.update_data("get_customer_360", total_outstanding=Decimal("200000"))
    case.tools.update_data(
        "get_transaction_summary", largest_counterparty_share=Decimal("0.80")
    )

    policy_envelope = case.tools.outputs["retrieve_credit_policy"]
    policy = policy_envelope.data
    assert isinstance(policy, CreditPolicyData)
    condition_codes = {
        RiskCode.REV_TXN_MISMATCH,
        RiskCode.PROFIT_CASHFLOW_MISMATCH,
        RiskCode.RECEIVABLES_SPIKE,
        RiskCode.INVENTORY_SPIKE,
        RiskCode.RECENT_DELINQUENCY,
        RiskCode.RESTRUCTURED_DEBT,
        RiskCode.LOW_LIMIT_UTILIZATION,
        RiskCode.HIGH_CUSTOMER_CONCENTRATION,
    }
    case.tools.outputs["retrieve_credit_policy"] = policy_envelope.model_copy(
        update={
            "data": policy.model_copy(update={"condition_flag_codes": condition_codes})
        }
    )

    result = run_credit_agent(case)

    assert result.recommendation.decision == Decision.PASS_WITH_CONDITIONS
    assert len(result.risk_flags) >= 8
    assert len(result.follow_up_questions) == 5
    assert_public_result_invariants(result)
