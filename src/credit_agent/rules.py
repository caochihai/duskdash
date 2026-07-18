"""Deterministic quality, reconciliation, risk, and decision rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from calendar import monthrange
from typing import Iterable

from .models import (
    CollateralSnapshotResult,
    Condition,
    ConditionStage,
    CreditFacilitiesResult,
    CreditPolicyData,
    CreditTaskInputV1,
    Customer360Result,
    DataConflict,
    DatasetQuality,
    Decision,
    FinancialMetricsResult,
    FinancialStatementsResult,
    FollowUpQuestion,
    FreshnessStatus,
    InfoRequest,
    QualityStatus,
    RepaymentHistoryResult,
    RiskCode,
    RiskFlag,
    RiskSeverity,
    ToolEnvelope,
    ToolStatus,
    TransactionSummaryResult,
)

EV_INPUT = "ev-input-request"
EV_POLICY = "ev-policy"
EV_CUSTOMER = "ev-customer-360"
EV_FACILITY = "ev-credit-facilities"
EV_REPAYMENT = "ev-repayment-history"
EV_TRANSACTION = "ev-transaction-summary"
EV_FINANCIALS = "ev-financial-statements"
EV_METRICS = "ev-financial-metrics"
EV_COLLATERAL = "ev-collateral"

MANDATORY_METRICS = {
    "revenue_growth",
    "profit_growth",
    "ebitda_growth",
    "gross_margin",
    "ebitda_margin",
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "debt_to_ebitda",
    "dscr",
    "interest_coverage",
    "receivable_days",
    "inventory_days",
    "payable_days",
    "operating_cash_flow",
    "free_cash_flow",
    "revenue_transaction_variance_ratio",
    "receivables_growth",
    "inventory_growth",
}

PLAN_METRICS = {
    "revenue_plan_variance",
    "ebitda_plan_variance",
    "operating_cash_flow_plan_variance",
}


@dataclass(slots=True)
class EvaluationInputs:
    task: CreditTaskInputV1
    policy_result: ToolEnvelope[CreditPolicyData]
    customer: Customer360Result
    facilities: CreditFacilitiesResult
    repayment: RepaymentHistoryResult
    transactions: TransactionSummaryResult
    statements: FinancialStatementsResult
    metrics: FinancialMetricsResult | None
    collateral: CollateralSnapshotResult | None


@dataclass(slots=True)
class Evaluation:
    decision: Decision
    risk_flags: list[RiskFlag]
    conditions: list[Condition]
    missing_information: list[str]
    follow_up_questions: list[FollowUpQuestion]
    info_requests: list[InfoRequest]
    datasets: dict[str, DatasetQuality]
    conflicts: list[DataConflict]
    metric_breaches: set[str] = field(default_factory=set)


def _metric(result: FinancialMetricsResult | None, name: str) -> Decimal | None:
    if result is None or result.data is None:
        return None
    item = result.data.metrics.get(name)
    return None if item is None else item.current


def _status_quality(result: ToolEnvelope[object] | None) -> DatasetQuality:
    if result is None:
        return DatasetQuality(
            status=QualityStatus.NOT_ASSESSED,
            freshness=FreshnessStatus.UNKNOWN,
            details=["Tool was not applicable or not called."],
        )
    if result.status == ToolStatus.OK:
        return DatasetQuality(status=QualityStatus.COMPLETE, freshness=FreshnessStatus.FRESH)
    if result.status == ToolStatus.PARTIAL:
        return DatasetQuality(
            status=QualityStatus.PARTIAL,
            freshness=FreshnessStatus.UNKNOWN,
            details=[
                f"Tool returned partial data with {len(result.warnings)} sanitized warning indicator(s)."
            ],
        )
    return DatasetQuality(
        status=QualityStatus.BLOCKED,
        freshness=FreshnessStatus.UNKNOWN,
        details=[f"Tool returned {result.status.value}; raw adapter errors are not exposed."],
    )


def _relative_difference(left: Decimal, right: Decimal) -> Decimal:
    denominator = max(abs(left), abs(right))
    if denominator == 0:
        return Decimal("0")
    return abs(left - right) / denominator


def _coverage_start(cutoff: date, months: int) -> date:
    month_index = cutoff.year * 12 + cutoff.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(cutoff.day, monthrange(year, month)[1])
    return date(year, month, day) + timedelta(days=1)


def evaluate_credit_case(inputs: EvaluationInputs, *, max_questions: int = 5) -> Evaluation:
    task = inputs.task
    policy = inputs.policy_result.data
    if policy is None:
        raise ValueError("evaluate_credit_case requires a policy payload")

    risk_flags: list[RiskFlag] = []
    conditions: list[Condition] = []
    missing: list[str] = []
    conflicts: list[DataConflict] = []
    info_requests: list[InfoRequest] = []
    question_candidates: list[tuple[int, FollowUpQuestion]] = []
    manual_review = False
    not_recommended = False
    metric_breaches: set[str] = set()

    def resolve_severity(code: RiskCode) -> RiskSeverity:
        severity = policy.severity_by_flag.get(code)
        if severity is None:
            missing.append(f"policy severity for risk flag: {code.value}")
            return RiskSeverity.HIGH
        return severity

    def add_flag(
        code: RiskCode,
        description: str,
        evidence_ids: list[str],
        question: FollowUpQuestion | None = None,
    ) -> None:
        risk_flags.append(
            RiskFlag(
                code=code,
                severity=resolve_severity(code),
                description=description,
                evidence_ids=evidence_ids,
                requires_clarification=question is not None,
            )
        )
        if question is not None:
            question_candidates.append((3, question))

    datasets: dict[str, DatasetQuality] = {
        "policy": _status_quality(inputs.policy_result),
        "customer_360": _status_quality(inputs.customer),
        "credit_facilities": _status_quality(inputs.facilities),
        "repayment_history": _status_quality(inputs.repayment),
        "transaction_summary": _status_quality(inputs.transactions),
        "financial_statements": _status_quality(inputs.statements),
        "financial_metrics": _status_quality(inputs.metrics),
    }
    if task.credit_request.collateral_required:
        datasets["collateral"] = _status_quality(inputs.collateral)

    all_results: list[tuple[str, ToolEnvelope[object], str]] = [
        ("policy", inputs.policy_result, EV_POLICY),
        ("customer_360", inputs.customer, EV_CUSTOMER),
        ("credit_facilities", inputs.facilities, EV_FACILITY),
        ("repayment_history", inputs.repayment, EV_REPAYMENT),
        ("transaction_summary", inputs.transactions, EV_TRANSACTION),
        ("financial_statements", inputs.statements, EV_FINANCIALS),
    ]
    if inputs.metrics is not None:
        all_results.append(("financial_metrics", inputs.metrics, EV_METRICS))
    if inputs.collateral is not None:
        all_results.append(("collateral", inputs.collateral, EV_COLLATERAL))

    for dataset_name, result, evidence_id in all_results:
        if result.status == ToolStatus.NO_DATA:
            missing.append(f"{dataset_name}: mandatory dataset returned NO_DATA")
            question_candidates.append(
                (
                    5,
                    FollowUpQuestion(
                        question=f"Provide the missing {dataset_name} dataset as of {task.as_of_date.isoformat()}.",
                        why_it_matters="The Credit Agent cannot complete the mandatory assessment without this dataset.",
                        expected_evidence=[dataset_name],
                        blocking_if_unanswered=True,
                        evidence_ids=[evidence_id],
                    ),
                )
            )
        elif result.status == ToolStatus.PARTIAL:
            conditions.append(
                Condition(
                    condition_code=f"PARTIAL_{dataset_name.upper()}",
                    description=f"Resolve the partial {dataset_name} response before approval review.",
                    blocking=True,
                    stage=ConditionStage.BEFORE_APPROVAL_REVIEW,
                    evidence_ids=[evidence_id],
                )
            )
            if dataset_name == "financial_statements":
                info_requests.append(
                    InfoRequest(
                        target_agent="document_intelligence_agent",
                        reason="Re-extract or verify partial financial-statement fields and provenance.",
                        evidence_ids=[evidence_id],
                    )
                )
        if result.as_of_date != task.as_of_date:
            manual_review = True
            datasets[dataset_name].status = QualityStatus.BLOCKED
            datasets[dataset_name].details.append(
                f"Tool cutoff {result.as_of_date.isoformat()} differs from locked cutoff {task.as_of_date.isoformat()}."
            )
            conflicts.append(
                DataConflict(
                    conflict_code=f"CUTOFF_MISMATCH_{dataset_name.upper()}",
                    description=f"{dataset_name} did not use the locked analysis cutoff date.",
                    evidence_ids=[EV_INPUT, evidence_id],
                )
            )

    threshold_names = [
        "repayment_min_coverage_months",
        "transaction_min_coverage_months",
        "max_internal_rating_age_days",
        "max_financial_statement_age_days",
        "outstanding_conflict_tolerance_ratio",
        "revenue_transaction_mismatch_threshold",
        "receivables_growth_threshold",
        "inventory_growth_threshold",
        "recent_delinquency_days",
        "maximum_late_payment_count",
        "maximum_inflow_volatility",
        "minimum_inflow_outflow_ratio",
        "low_limit_utilization_threshold",
        "high_customer_concentration_threshold",
        "minimum_dscr",
        "maximum_debt_to_equity",
        "minimum_interest_coverage",
        "maximum_tenor_months",
        "maximum_requested_limit",
    ]
    if task.credit_request.collateral_required:
        threshold_names.extend(
            [
                "max_collateral_valuation_age_days",
                "minimum_collateral_coverage",
                "collateral_coverage_tolerance_ratio",
            ]
        )
    absent_thresholds = [
        name for name in threshold_names if getattr(policy.thresholds, name) is None
    ]
    if absent_thresholds:
        datasets["policy"].status = QualityStatus.BLOCKED
        datasets["policy"].details.append("Active policy is missing typed thresholds.")
        missing.append("active policy thresholds: " + ", ".join(absent_thresholds))
        question_candidates.append(
            (
                1,
                FollowUpQuestion(
                    question="Publish the missing typed thresholds in the active credit policy response.",
                    why_it_matters="The agent must not substitute hard-coded lending thresholds.",
                    expected_evidence=absent_thresholds,
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_POLICY],
                ),
            )
        )

    statements = inputs.statements.data
    if (
        statements is not None
        and statements.current is not None
        and statements.prior is not None
    ):
        datasets["financial_statements"].details.append(
            "Audit status: "
            f"current={'audited' if statements.current.audited else 'unaudited'}, "
            f"prior={'audited' if statements.prior.audited else 'unaudited'}."
        )
        if policy.require_audited_financial_statements and (
            not statements.current.audited or not statements.prior.audited
        ):
            datasets["financial_statements"].status = QualityStatus.BLOCKED
            missing.append("audited current and prior financial statements")
            question_candidates.append(
                (
                    0,
                    FollowUpQuestion(
                        question="Provide audited current and prior financial statements as required by active policy.",
                        why_it_matters="The active policy does not permit an eligibility decision based on unaudited statements.",
                        expected_evidence=[
                            "audited_current_financial_statement",
                            "audited_prior_financial_statement",
                        ],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_FINANCIALS, EV_POLICY],
                    ),
                )
            )
    if statements is None or statements.current is None:
        risk_flags.append(
            RiskFlag(
                code=RiskCode.MISSING_LATEST_FINANCIALS,
                severity=resolve_severity(RiskCode.MISSING_LATEST_FINANCIALS),
                description="The latest financial statement is unavailable.",
                evidence_ids=[EV_FINANCIALS],
                requires_clarification=True,
            )
        )
        missing.append("latest financial statement")
    if statements is None or statements.prior is None:
        missing.append("prior-period financial statement")
    if statements is None or statements.current is None or statements.prior is None:
        datasets["financial_statements"].status = QualityStatus.BLOCKED
        datasets["financial_statements"].freshness = FreshnessStatus.UNKNOWN
        datasets["financial_statements"].details.append(
            "Current and prior-period statements are both mandatory."
        )
        info_requests.append(
            InfoRequest(
                target_agent="document_intelligence_agent",
                reason="Provide structured current and prior-period financial statements; Credit Agent does not parse raw documents.",
                evidence_ids=[EV_FINANCIALS],
            )
        )
        question_candidates.append(
            (
                0,
                FollowUpQuestion(
                    question="Provide structured current and prior-period financial statements with source references.",
                    why_it_matters="A single-period snapshot cannot support a positive renewal recommendation.",
                    expected_evidence=["current_financial_statement", "prior_financial_statement"],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_FINANCIALS],
                ),
            )
        )
    elif policy.thresholds.max_financial_statement_age_days is not None:
        if statements.current.currency != task.credit_request.currency:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="FINANCIAL_STATEMENT_CURRENCY_CONFLICT",
                    description="Financial statements and the credit request use different currencies without an authoritative FX tool.",
                    evidence_ids=[EV_INPUT, EV_FINANCIALS],
                )
            )
        if statements.current.period_end > task.as_of_date:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="POST_CUTOFF_FINANCIAL_STATEMENT",
                    description="The current financial period ends after the locked analysis cutoff.",
                    evidence_ids=[EV_INPUT, EV_FINANCIALS],
                )
            )
        age = (task.as_of_date - statements.current.period_end).days
        if age > policy.thresholds.max_financial_statement_age_days:
            datasets["financial_statements"].freshness = FreshnessStatus.STALE
            conditions.append(
                Condition(
                    condition_code="STALE_FINANCIAL_STATEMENTS",
                    description="Obtain financial statements within the active policy freshness window.",
                    blocking=True,
                    stage=ConditionStage.BEFORE_APPROVAL_REVIEW,
                    evidence_ids=[EV_FINANCIALS, EV_POLICY],
                )
            )

    required_metrics = MANDATORY_METRICS | set(policy.required_metrics)
    if statements is not None and statements.plan is not None:
        required_metrics |= PLAN_METRICS
    if inputs.metrics is None or inputs.metrics.data is None:
        missing.append("deterministic financial metrics")
        datasets["financial_metrics"].status = QualityStatus.BLOCKED
        datasets["financial_metrics"].details.append(
            "The deterministic calculator did not return a usable result."
        )
    else:
        available = set(inputs.metrics.data.metrics)
        unavailable = (
            required_metrics - available
        ) | set(inputs.metrics.data.non_computable_metrics) | {
            name
            for name in required_metrics & available
            if inputs.metrics.data.metrics[name].current is None
            or inputs.metrics.data.metrics[name].prior is None
        }
        if statements is not None and statements.plan is not None:
            unavailable |= {
                name
                for name in PLAN_METRICS & available
                if inputs.metrics.data.metrics[name].plan is None
                or inputs.metrics.data.metrics[name].plan_variance is None
            }
        if unavailable or inputs.metrics.data.missing_inputs:
            datasets["financial_metrics"].status = QualityStatus.BLOCKED
            datasets["financial_metrics"].details.append(
                "One or more mandatory metrics are absent or non-computable."
            )
            missing.append(
                "computable financial metrics: " + ", ".join(sorted(unavailable or set(inputs.metrics.data.missing_inputs)))
            )

    repayment = inputs.repayment.data
    if repayment is not None and policy.thresholds.repayment_min_coverage_months is not None:
        if repayment.coverage_period.end_date > task.as_of_date:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="POST_CUTOFF_REPAYMENT_DATA",
                    description="Repayment history includes a period after the locked analysis cutoff.",
                    evidence_ids=[EV_INPUT, EV_REPAYMENT],
                )
            )
        repayment_window_incomplete = (
            repayment.lookback_months
            < policy.thresholds.repayment_min_coverage_months
            or repayment.coverage_period.end_date < task.as_of_date
            or repayment.coverage_period.start_date
            > _coverage_start(
                task.as_of_date, policy.thresholds.repayment_min_coverage_months
            )
        )
        if repayment_window_incomplete:
            datasets["repayment_history"].status = QualityStatus.BLOCKED
            datasets["repayment_history"].freshness = FreshnessStatus.STALE
            datasets["repayment_history"].details.append(
                "Coverage does not end at the cutoff or is shorter than policy requires."
            )
            missing.append("repayment history policy lookback window ending at as_of_date")
            question_candidates.append(
                (
                    2,
                    FollowUpQuestion(
                        question="Provide repayment history covering the full policy-defined lookback window.",
                        why_it_matters="Recent payment behavior cannot be assessed from the returned shortened window.",
                        expected_evidence=["repayment_history_full_window"],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_REPAYMENT, EV_POLICY],
                    ),
                )
            )

    transactions = inputs.transactions.data
    if transactions is not None and policy.thresholds.transaction_min_coverage_months is not None:
        if transactions.coverage_period.end_date > task.as_of_date:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="POST_CUTOFF_TRANSACTION_DATA",
                    description="Transaction summary includes a period after the locked analysis cutoff.",
                    evidence_ids=[EV_INPUT, EV_TRANSACTION],
                )
            )
        transaction_window_incomplete = (
            transactions.coverage_months
            < policy.thresholds.transaction_min_coverage_months
            or transactions.coverage_period.end_date < task.as_of_date
            or transactions.coverage_period.start_date
            > _coverage_start(
                task.as_of_date, policy.thresholds.transaction_min_coverage_months
            )
        )
        if transaction_window_incomplete:
            datasets["transaction_summary"].status = QualityStatus.BLOCKED
            datasets["transaction_summary"].freshness = FreshnessStatus.STALE
            datasets["transaction_summary"].details.append(
                "Coverage does not end at the cutoff or is shorter than policy requires."
            )
            missing.append("transaction history policy coverage window ending at as_of_date")
            question_candidates.append(
                (
                    2,
                    FollowUpQuestion(
                        question="Provide transaction summaries covering the full policy-defined window.",
                        why_it_matters="Cash-flow level, volatility, and concentration require the complete coverage window.",
                        expected_evidence=["transaction_summary_full_window"],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_TRANSACTION, EV_POLICY],
                    ),
                )
            )

    customer = inputs.customer.data
    facilities = inputs.facilities.data
    tolerance = policy.thresholds.outstanding_conflict_tolerance_ratio
    if customer is not None:
        if customer.rating_as_of > task.as_of_date:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="POST_CUTOFF_CUSTOMER_RATING",
                    description="The internal rating is dated after the locked analysis cutoff.",
                    evidence_ids=[EV_INPUT, EV_CUSTOMER],
                )
            )
        elif (
            policy.thresholds.max_internal_rating_age_days is not None
            and (task.as_of_date - customer.rating_as_of).days
            > policy.thresholds.max_internal_rating_age_days
        ):
            datasets["customer_360"].freshness = FreshnessStatus.STALE
            add_flag(
                RiskCode.STALE_INTERNAL_RATING,
                "The internal rating is older than the active policy freshness limit.",
                [EV_CUSTOMER, EV_POLICY],
                FollowUpQuestion(
                    question="Provide a refreshed internal rating as of the locked analysis cutoff.",
                    why_it_matters="Credit eligibility cannot silently rely on a rating outside the policy freshness window.",
                    expected_evidence=["refreshed_internal_rating"],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_CUSTOMER, EV_POLICY],
                ),
            )
        if (
            "*" not in policy.allowed_internal_ratings
            and customer.internal_rating not in policy.allowed_internal_ratings
        ):
            add_flag(
                RiskCode.INTERNAL_RATING_OUTSIDE_POLICY,
                "The authoritative internal rating is outside the active policy's allowed set.",
                [EV_CUSTOMER, EV_POLICY],
                FollowUpQuestion(
                    question="Confirm the internal rating and provide its active-policy treatment.",
                    why_it_matters="A rating outside the policy's allowed set cannot silently pass renewal review.",
                    expected_evidence=["confirmed_internal_rating", "policy_rating_treatment"],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_CUSTOMER, EV_POLICY],
                ),
            )
        if (
            "*" not in policy.allowed_relationship_statuses
            and customer.relationship_status
            not in policy.allowed_relationship_statuses
        ):
            add_flag(
                RiskCode.RELATIONSHIP_STATUS_OUTSIDE_POLICY,
                "The authoritative relationship status is outside the active policy's allowed set.",
                [EV_CUSTOMER, EV_POLICY],
                FollowUpQuestion(
                    question="Confirm the relationship status and provide its active-policy treatment.",
                    why_it_matters="A blocked or otherwise ineligible relationship cannot silently pass credit review.",
                    expected_evidence=[
                        "confirmed_relationship_status",
                        "policy_relationship_treatment",
                    ],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_CUSTOMER, EV_POLICY],
                ),
            )

    if facilities is not None:
        matching_facilities = [
            facility
            for facility in facilities.facilities
            if facility.product_code == task.credit_request.product_code
        ]
        if not matching_facilities:
            missing.append("facility record matching the requested product")
            datasets["credit_facilities"].status = QualityStatus.BLOCKED
            datasets["credit_facilities"].details.append(
                "No returned facility record matches the submitted product code."
            )
            question_candidates.append(
                (
                    0,
                    FollowUpQuestion(
                        question="Provide the authoritative facility record for the submitted product code.",
                        why_it_matters="A renewal or limit review cannot use aggregates from unrelated products.",
                        expected_evidence=["matching_product_facility_record"],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_INPUT, EV_FACILITY],
                    ),
                )
            )
        else:
            matching_currencies = {facility.currency for facility in matching_facilities}
            matched_approved_limit = sum(
                (facility.approved_limit for facility in matching_facilities),
                start=Decimal("0"),
            )
            matched_outstanding = sum(
                (facility.outstanding for facility in matching_facilities),
                start=Decimal("0"),
            )
            matched_utilization = (
                Decimal("0")
                if matched_approved_limit == 0 and matched_outstanding == 0
                else (
                    None
                    if matched_approved_limit == 0
                    else matched_outstanding / matched_approved_limit
                )
            )
            product_aggregate_conflict = (
                len(matching_currencies) != 1
                or facilities.currency not in matching_currencies
                or facilities.currency != task.credit_request.currency
                or matched_utilization is None
                or _relative_difference(
                    facilities.approved_limit, matched_approved_limit
                )
                > (tolerance or Decimal("0"))
                or _relative_difference(facilities.outstanding, matched_outstanding)
                > (tolerance or Decimal("0"))
                or _relative_difference(
                    facilities.utilization_ratio, matched_utilization
                )
                > (tolerance or Decimal("0"))
            )
            if product_aggregate_conflict:
                manual_review = True
                datasets["credit_facilities"].status = QualityStatus.BLOCKED
                datasets["credit_facilities"].details.append(
                    "Requested-product facility records do not reconcile to the returned aggregate."
                )
                conflicts.append(
                    DataConflict(
                        conflict_code="REQUESTED_PRODUCT_FACILITY_CONFLICT",
                        description=(
                            "Requested-product facility records differ materially from "
                            "the aggregate used for limit, outstanding, utilization, or currency."
                        ),
                        evidence_ids=[EV_INPUT, EV_FACILITY, EV_POLICY],
                    )
                )
        utilization_inconsistent = (
            any(
                (
                    facility.approved_limit == 0
                    and facility.utilization_ratio != 0
                )
                or (
                    tolerance is not None
                    and _relative_difference(
                        facility.outstanding,
                        facility.approved_limit * facility.utilization_ratio,
                    )
                    > tolerance
                )
                for facility in facilities.facilities
            )
        )
        if utilization_inconsistent:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="FACILITY_UTILIZATION_CONFLICT",
                    description="Reported facility utilization is inconsistent with approved limit and outstanding exposure.",
                    evidence_ids=[EV_FACILITY, EV_POLICY],
                )
            )
        if (
            facilities.outstanding > facilities.approved_limit
            or facilities.utilization_ratio > Decimal("1")
            or any(
                facility.outstanding > facility.approved_limit
                or facility.utilization_ratio > Decimal("1")
                for facility in facilities.facilities
            )
        ):
            add_flag(
                RiskCode.OVER_LIMIT_EXPOSURE,
                "Facility exposure or utilization exceeds its approved limit.",
                [EV_FACILITY, EV_POLICY],
                FollowUpQuestion(
                    question="Reconcile the over-limit exposure and provide the active-policy treatment or approved exception.",
                    why_it_matters="Exposure above an approved limit requires an explicit policy disposition.",
                    expected_evidence=[
                        "over_limit_reconciliation",
                        "approved_exception_or_policy_treatment",
                    ],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_FACILITY, EV_POLICY],
                ),
            )

    if customer is not None and facilities is not None:
        if (
            "*" not in policy.applicable_segments
            and customer.segment not in policy.applicable_segments
        ):
            missing.append("active policy applicable to customer segment")
            datasets["policy"].status = QualityStatus.BLOCKED
            datasets["policy"].details.append(
                "Policy applicability does not include the returned customer segment."
            )
        currencies = {
            task.credit_request.currency,
            customer.currency,
            facilities.currency,
        }
        currency_evidence = [EV_INPUT, EV_CUSTOMER, EV_FACILITY]
        if transactions is not None:
            currencies.add(transactions.currency)
            currency_evidence.append(EV_TRANSACTION)
        if len(currencies) > 1:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="CURRENCY_CONFLICT",
                    description="Source amounts use different currencies and no authoritative FX tool is available.",
                    evidence_ids=currency_evidence,
                )
            )
        if tolerance is not None and _relative_difference(
            customer.total_outstanding, facilities.outstanding
        ) > tolerance:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="OUTSTANDING_BALANCE_CONFLICT",
                    description="Customer 360 and the loan ledger return materially different outstanding balances.",
                    evidence_ids=[EV_CUSTOMER, EV_FACILITY],
                )
            )
            risk_flags.append(
                RiskFlag(
                    code=RiskCode.FINANCIAL_DATA_CONFLICT,
                    severity=resolve_severity(RiskCode.FINANCIAL_DATA_CONFLICT),
                    description="Outstanding balances conflict across mandatory sources.",
                    evidence_ids=[EV_CUSTOMER, EV_FACILITY],
                    requires_clarification=True,
                )
            )
            question_candidates.append(
                (
                    0,
                    FollowUpQuestion(
                        question="Reconcile the Customer 360 exposure with the loan-ledger outstanding balance at the locked cutoff.",
                        why_it_matters="The agent must not choose one of two conflicting exposure values.",
                        expected_evidence=["loan_ledger_reconciliation", "exposure_breakdown"],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_CUSTOMER, EV_FACILITY],
                    ),
                )
            )
        if facilities.ledger_as_of != task.as_of_date:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="LOAN_LEDGER_CUTOFF_CONFLICT",
                    description="The loan-ledger payload is not aligned to the locked analysis cutoff.",
                    evidence_ids=[EV_INPUT, EV_FACILITY],
                )
            )
        if tolerance is not None and _relative_difference(
            task.credit_request.current_limit, facilities.approved_limit
        ) > tolerance:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="CURRENT_LIMIT_CONFLICT",
                    description="The submitted current limit conflicts with the facility system value.",
                    evidence_ids=[EV_INPUT, EV_FACILITY],
                )
            )
        if (
            tolerance is not None
            and statements is not None
            and statements.current is not None
            and statements.current.total_debt is not None
            and statements.current.currency == facilities.currency
        ):
            reported_debt = (
                statements.current.total_debt * statements.current.unit_multiplier
            )
            if (
                reported_debt < facilities.outstanding
                and _relative_difference(reported_debt, facilities.outstanding) > tolerance
            ):
                manual_review = True
                conflicts.append(
                    DataConflict(
                        conflict_code="FINANCIAL_DEBT_BELOW_LEDGER",
                        description="Reported total debt is materially below the authoritative facility outstanding balance.",
                        evidence_ids=[EV_FINANCIALS, EV_FACILITY],
                    )
                )
                risk_flags.append(
                    RiskFlag(
                        code=RiskCode.FINANCIAL_DATA_CONFLICT,
                        severity=resolve_severity(RiskCode.FINANCIAL_DATA_CONFLICT),
                        description="Financial-statement debt conflicts with the facility ledger.",
                        evidence_ids=[EV_FINANCIALS, EV_FACILITY],
                        requires_clarification=True,
                    )
                )

    variance = _metric(inputs.metrics, "revenue_transaction_variance_ratio")
    if (
        variance is not None
        and policy.thresholds.revenue_transaction_mismatch_threshold is not None
        and variance > policy.thresholds.revenue_transaction_mismatch_threshold
    ):
        add_flag(
            RiskCode.REV_TXN_MISMATCH,
            "Reported revenue and bank transaction inflow exceed the policy mismatch tolerance.",
            [EV_METRICS, EV_TRANSACTION, EV_FINANCIALS],
            FollowUpQuestion(
                question="Explain the revenue-to-bank-inflow mismatch and provide receivables aging or evidence of collections through other banks.",
                why_it_matters="The mismatch can indicate uncollected revenue or incomplete cash-flow visibility.",
                expected_evidence=["receivables_aging", "other_bank_inflow_summary"],
                blocking_if_unanswered=True,
                evidence_ids=[EV_METRICS, EV_TRANSACTION, EV_FINANCIALS],
            ),
        )

    if (
        statements is not None
        and statements.current is not None
        and statements.current.net_profit is not None
        and statements.current.operating_cash_flow is not None
        and statements.current.net_profit > 0
        and statements.current.operating_cash_flow < 0
    ):
        add_flag(
            RiskCode.PROFIT_CASHFLOW_MISMATCH,
            "Net profit is positive while operating cash flow is negative.",
            [EV_FINANCIALS, EV_METRICS],
            FollowUpQuestion(
                question="Explain why positive profit did not convert to operating cash and provide receivables and inventory movements.",
                why_it_matters="Debt service depends on realized operating cash rather than accounting profit alone.",
                expected_evidence=["receivables_movement", "inventory_movement", "cashflow_reconciliation"],
                blocking_if_unanswered=True,
                evidence_ids=[EV_FINANCIALS, EV_METRICS],
            ),
        )

    receivables_growth = _metric(inputs.metrics, "receivables_growth")
    if (
        receivables_growth is not None
        and policy.thresholds.receivables_growth_threshold is not None
        and receivables_growth > policy.thresholds.receivables_growth_threshold
    ):
        add_flag(
            RiskCode.RECEIVABLES_SPIKE,
            "Receivables growth exceeds the active policy threshold.",
            [EV_METRICS, EV_FINANCIALS],
            FollowUpQuestion(
                question="Provide receivables aging and the largest debtor balances at the cutoff date.",
                why_it_matters="The increase may weaken cash conversion and debt-service capacity.",
                expected_evidence=["receivables_aging", "largest_debtors"],
                blocking_if_unanswered=True,
                evidence_ids=[EV_METRICS, EV_FINANCIALS],
            ),
        )

    inventory_growth = _metric(inputs.metrics, "inventory_growth")
    if (
        inventory_growth is not None
        and policy.thresholds.inventory_growth_threshold is not None
        and inventory_growth > policy.thresholds.inventory_growth_threshold
    ):
        add_flag(
            RiskCode.INVENTORY_SPIKE,
            "Inventory growth exceeds the active policy threshold.",
            [EV_METRICS, EV_FINANCIALS],
            FollowUpQuestion(
                question="Provide inventory aging and explain the increase relative to sales demand.",
                why_it_matters="Slow-moving inventory can absorb working capital and reduce repayment capacity.",
                expected_evidence=["inventory_aging", "sales_plan"],
                blocking_if_unanswered=True,
                evidence_ids=[EV_METRICS, EV_FINANCIALS],
            ),
        )

    if repayment is not None:
        delinquency_threshold = policy.thresholds.recent_delinquency_days
        if delinquency_threshold is not None and (
            repayment.max_days_past_due >= delinquency_threshold
            or repayment.current_days_past_due >= delinquency_threshold
        ):
            add_flag(
                RiskCode.RECENT_DELINQUENCY,
                "Repayment history meets the active policy definition of recent delinquency.",
                [EV_REPAYMENT, EV_POLICY],
                FollowUpQuestion(
                    question="Explain the recent delinquency and provide evidence that overdue obligations have been regularized.",
                    why_it_matters="Recent payment behavior directly affects renewal risk.",
                    expected_evidence=["delinquency_explanation", "payment_confirmation"],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_REPAYMENT],
                ),
            )
        maximum_late_count = policy.thresholds.maximum_late_payment_count
        if (
            maximum_late_count is not None
            and repayment.late_payment_count > maximum_late_count
        ):
            add_flag(
                RiskCode.REPEATED_LATE_PAYMENTS,
                "The count of late-payment events exceeds the active policy threshold.",
                [EV_REPAYMENT, EV_POLICY],
                FollowUpQuestion(
                    question="Explain the repeated late payments and provide evidence of normalized repayment performance.",
                    why_it_matters="Repeated short delinquencies can be material even when no single event reaches the DPD threshold.",
                    expected_evidence=[
                        "late_payment_explanation",
                        "normalized_repayment_evidence",
                    ],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_REPAYMENT, EV_POLICY],
                ),
            )
        if repayment.restructured_debt:
            add_flag(
                RiskCode.RESTRUCTURED_DEBT,
                "The repayment source reports restructured debt.",
                [EV_REPAYMENT],
                FollowUpQuestion(
                    question="Provide the restructuring decision, revised schedule, and post-restructuring repayment performance.",
                    why_it_matters="The agent needs the documented terms and subsequent performance to assess debt service.",
                    expected_evidence=["restructuring_decision", "revised_schedule", "post_restructure_history"],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_REPAYMENT],
                ),
            )

    if facilities is not None and policy.thresholds.low_limit_utilization_threshold is not None:
        if facilities.utilization_ratio < policy.thresholds.low_limit_utilization_threshold:
            add_flag(
                RiskCode.LOW_LIMIT_UTILIZATION,
                "Historical facility utilization is below the active policy threshold.",
                [EV_FACILITY, EV_POLICY],
                FollowUpQuestion(
                    question="Explain why the full requested limit is needed despite low historical utilization and provide a working-capital forecast.",
                    why_it_matters="The requested amount should be consistent with demonstrated funding need.",
                    expected_evidence=["working_capital_forecast", "drawdown_plan"],
                    blocking_if_unanswered=False,
                    evidence_ids=[EV_INPUT, EV_FACILITY],
                ),
            )

    if transactions is not None:
        maximum_volatility = policy.thresholds.maximum_inflow_volatility
        if (
            maximum_volatility is not None
            and transactions.inflow_volatility > maximum_volatility
        ):
            add_flag(
                RiskCode.HIGH_INFLOW_VOLATILITY,
                "Transaction inflow volatility exceeds the active policy threshold.",
                [EV_TRANSACTION, EV_POLICY],
                FollowUpQuestion(
                    question="Explain the cash-inflow volatility and provide a supported cash forecast.",
                    why_it_matters="Unstable inflows can weaken debt-service capacity even when annual totals appear adequate.",
                    expected_evidence=["cash_inflow_explanation", "supported_cash_forecast"],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_TRANSACTION, EV_POLICY],
                ),
            )
        minimum_cash_ratio = policy.thresholds.minimum_inflow_outflow_ratio
        if (
            minimum_cash_ratio is not None
            and transactions.average_monthly_inflow
            < transactions.average_monthly_outflow * minimum_cash_ratio
        ):
            add_flag(
                RiskCode.LOW_TRANSACTION_CASH_COVERAGE,
                "Average transaction inflow does not cover outflow at the active policy ratio.",
                [EV_TRANSACTION, EV_POLICY],
                FollowUpQuestion(
                    question="Reconcile the negative transaction cash margin and provide the repayment funding source.",
                    why_it_matters="Observed bank inflows below outflows can contradict the claimed repayment capacity.",
                    expected_evidence=[
                        "transaction_cash_reconciliation",
                        "repayment_funding_source",
                    ],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_TRANSACTION, EV_POLICY],
                ),
            )
        concentration_threshold = policy.thresholds.high_customer_concentration_threshold
        if (
            concentration_threshold is not None
            and transactions.largest_counterparty_share > concentration_threshold
        ):
            add_flag(
                RiskCode.HIGH_CUSTOMER_CONCENTRATION,
                "Largest-counterparty concentration exceeds the active policy threshold.",
                [EV_TRANSACTION, EV_POLICY],
                FollowUpQuestion(
                    question="Provide the largest counterparty contract, payment history, and diversification plan.",
                    why_it_matters="Concentration can make repayment capacity sensitive to one counterparty.",
                    expected_evidence=["largest_counterparty_contract", "counterparty_payment_history", "diversification_plan"],
                    blocking_if_unanswered=False,
                    evidence_ids=[EV_TRANSACTION],
                ),
            )
        if transactions.related_party_flow:
            add_flag(
                RiskCode.RELATED_PARTY_FLOW,
                "The transaction summary contains a related-party-flow indicator requiring Compliance review.",
                [EV_TRANSACTION],
            )
            manual_review = True
            info_requests.append(
                InfoRequest(
                    target_agent="compliance_agent",
                    reason="Assess the related-party-flow indicator; Credit Agent makes no AML, fraud, or legal finding.",
                    evidence_ids=[EV_TRANSACTION],
                )
            )

    collateral = None if inputs.collateral is None else inputs.collateral.data
    if task.credit_request.collateral_required and collateral is not None:
        if collateral.valuation_date > task.as_of_date:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="POST_CUTOFF_COLLATERAL_VALUATION",
                    description="Collateral valuation is dated after the locked analysis cutoff.",
                    evidence_ids=[EV_INPUT, EV_COLLATERAL],
                )
            )
        if collateral.currency != task.credit_request.currency:
            manual_review = True
            conflicts.append(
                DataConflict(
                    conflict_code="COLLATERAL_CURRENCY_CONFLICT",
                    description="Collateral and credit request currencies differ and no authoritative FX tool is available.",
                    evidence_ids=[EV_INPUT, EV_COLLATERAL],
                )
            )
        if (
            "*" not in policy.allowed_collateral_valuation_statuses
            and collateral.valuation_status
            not in policy.allowed_collateral_valuation_statuses
        ):
            add_flag(
                RiskCode.COLLATERAL_STATUS_OUTSIDE_POLICY,
                "The collateral valuation status is outside the active policy's allowed set.",
                [EV_COLLATERAL, EV_POLICY],
                FollowUpQuestion(
                    question="Provide a collateral valuation with an allowed status or an explicit policy treatment.",
                    why_it_matters="Collateral coverage cannot silently rely on an ineligible valuation status.",
                    expected_evidence=[
                        "eligible_collateral_valuation",
                        "policy_collateral_status_treatment",
                    ],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_COLLATERAL, EV_POLICY],
                ),
            )
        if (
            "*" not in policy.allowed_collateral_coverage_bases
            and collateral.coverage_basis
            not in policy.allowed_collateral_coverage_bases
        ):
            manual_review = True
            datasets["collateral"].status = QualityStatus.BLOCKED
            datasets["collateral"].details.append(
                "Collateral coverage basis is outside the active policy's allowed set."
            )
            conflicts.append(
                DataConflict(
                    conflict_code="COLLATERAL_COVERAGE_BASIS_OUTSIDE_POLICY",
                    description="Collateral coverage basis is not permitted by active policy.",
                    evidence_ids=[EV_COLLATERAL, EV_POLICY],
                )
            )
        expected_coverage = collateral.eligible_value / collateral.coverage_denominator
        coverage_tolerance = policy.thresholds.collateral_coverage_tolerance_ratio
        if _relative_difference(collateral.coverage_ratio, expected_coverage) > (
            coverage_tolerance or Decimal("0")
        ):
            manual_review = True
            datasets["collateral"].status = QualityStatus.BLOCKED
            datasets["collateral"].details.append(
                "Reported collateral coverage ratio does not reconcile to eligible value and denominator."
            )
            conflicts.append(
                DataConflict(
                    conflict_code="COLLATERAL_COVERAGE_RATIO_CONFLICT",
                    description=(
                        "Collateral coverage ratio is inconsistent with eligible value "
                        "and the declared coverage denominator."
                    ),
                    evidence_ids=[EV_COLLATERAL, EV_POLICY],
                )
            )
        if (
            collateral.coverage_basis == "requested_limit"
            and collateral.coverage_denominator != task.credit_request.requested_limit
        ):
            manual_review = True
            datasets["collateral"].status = QualityStatus.BLOCKED
            datasets["collateral"].details.append(
                "Requested-limit collateral basis does not use the submitted requested limit."
            )
            conflicts.append(
                DataConflict(
                    conflict_code="COLLATERAL_COVERAGE_DENOMINATOR_CONFLICT",
                    description=(
                        "Collateral declares requested_limit basis but uses a different "
                        "coverage denominator."
                    ),
                    evidence_ids=[EV_INPUT, EV_COLLATERAL],
                )
            )
        max_age = policy.thresholds.max_collateral_valuation_age_days
        if max_age is not None and (task.as_of_date - collateral.valuation_date).days > max_age:
            datasets["collateral"].freshness = FreshnessStatus.STALE
            add_flag(
                RiskCode.STALE_COLLATERAL_VALUATION,
                "Collateral valuation is older than the active policy freshness limit.",
                [EV_COLLATERAL, EV_POLICY],
                FollowUpQuestion(
                    question="Provide a refreshed collateral valuation meeting the active policy freshness requirement.",
                    why_it_matters="Coverage cannot be relied on using an out-of-date valuation.",
                    expected_evidence=["updated_collateral_valuation"],
                    blocking_if_unanswered=True,
                    evidence_ids=[EV_COLLATERAL, EV_POLICY],
                ),
            )
        minimum_coverage = policy.thresholds.minimum_collateral_coverage
        if minimum_coverage is not None and collateral.coverage_ratio < minimum_coverage:
            metric_breaches.add("collateral_coverage")

    dscr = _metric(inputs.metrics, "dscr")
    if dscr is not None and policy.thresholds.minimum_dscr is not None and dscr < policy.thresholds.minimum_dscr:
        metric_breaches.add("dscr")
    leverage = _metric(inputs.metrics, "debt_to_equity")
    if (
        leverage is not None
        and policy.thresholds.maximum_debt_to_equity is not None
        and leverage > policy.thresholds.maximum_debt_to_equity
    ):
        metric_breaches.add("debt_to_equity")
    interest_coverage = _metric(inputs.metrics, "interest_coverage")
    if (
        interest_coverage is not None
        and policy.thresholds.minimum_interest_coverage is not None
        and interest_coverage < policy.thresholds.minimum_interest_coverage
    ):
        metric_breaches.add("interest_coverage")
    if (
        policy.thresholds.maximum_tenor_months is not None
        and task.credit_request.requested_tenor_months
        > policy.thresholds.maximum_tenor_months
    ):
        metric_breaches.add("requested_tenor_months")
    if (
        policy.thresholds.maximum_requested_limit is not None
        and task.credit_request.requested_limit
        > policy.thresholds.maximum_requested_limit
    ):
        metric_breaches.add("requested_limit")

    for metric_name in sorted(metric_breaches):
        ids = [EV_METRICS, EV_POLICY]
        if metric_name == "collateral_coverage":
            ids = [EV_COLLATERAL, EV_POLICY]
        if metric_name in policy.not_recommended_metric_names:
            not_recommended = True
        elif metric_name in policy.condition_metric_names:
            conditions.append(
                Condition(
                    condition_code=f"POLICY_{metric_name.upper()}_BREACH",
                    description=f"Resolve the active-policy breach for {metric_name} before proceeding.",
                    blocking=True,
                    stage=ConditionStage.BEFORE_APPROVAL_REVIEW,
                    evidence_ids=ids,
                )
            )
        else:
            manual_review = True
            missing.append(f"policy treatment for metric breach: {metric_name}")

    for flag in risk_flags:
        if flag.code in policy.not_recommended_flag_codes:
            not_recommended = True
        elif flag.code in policy.condition_flag_codes:
            conditions.append(
                Condition(
                    condition_code=f"RESOLVE_{flag.code.value}",
                    description=f"Resolve or accept the documented {flag.code.value} risk under active policy.",
                    blocking=flag.severity == RiskSeverity.HIGH,
                    stage=ConditionStage.BEFORE_APPROVAL_REVIEW,
                    evidence_ids=flag.evidence_ids,
                )
            )
        elif flag.code not in {
            RiskCode.MISSING_LATEST_FINANCIALS,
            RiskCode.FINANCIAL_DATA_CONFLICT,
            RiskCode.RELATED_PARTY_FLOW,
        }:
            manual_review = True
            missing.append(f"policy treatment for risk flag: {flag.code.value}")

    if missing:
        decision = Decision.NEEDS_INFO
    elif manual_review or conflicts:
        decision = Decision.MANUAL_REVIEW
    elif not_recommended:
        decision = Decision.NOT_RECOMMENDED
    elif conditions:
        decision = Decision.PASS_WITH_CONDITIONS
    else:
        decision = Decision.READY_FOR_APPROVAL_REVIEW

    # Stable ordering makes the outcome independent of tool completion order.
    deduped_missing = list(dict.fromkeys(missing))
    deduped_conditions: list[Condition] = []
    seen_conditions: set[str] = set()
    for condition in conditions:
        if condition.condition_code not in seen_conditions:
            seen_conditions.add(condition.condition_code)
            deduped_conditions.append(condition)
    questions = [
        item[1][1]
        for item in sorted(
            enumerate(question_candidates),
            key=lambda pair: (pair[1][0], pair[0]),
        )[:max_questions]
    ]
    return Evaluation(
        decision=decision,
        risk_flags=risk_flags,
        conditions=deduped_conditions,
        missing_information=deduped_missing,
        follow_up_questions=questions,
        info_requests=info_requests,
        datasets=datasets,
        conflicts=conflicts,
        metric_breaches=metric_breaches,
    )


def aggregate_quality(datasets: Iterable[DatasetQuality]) -> tuple[QualityStatus, FreshnessStatus]:
    values = list(datasets)
    if not values:
        return QualityStatus.NOT_ASSESSED, FreshnessStatus.UNKNOWN
    if any(item.status == QualityStatus.BLOCKED for item in values):
        overall = QualityStatus.BLOCKED
    elif any(item.status == QualityStatus.NOT_ASSESSED for item in values):
        overall = QualityStatus.BLOCKED
    elif any(item.status == QualityStatus.PARTIAL for item in values):
        overall = QualityStatus.PARTIAL
    else:
        overall = QualityStatus.COMPLETE
    freshnesses = {item.freshness for item in values}
    if FreshnessStatus.STALE in freshnesses:
        freshness = (
            FreshnessStatus.STALE
            if freshnesses <= {FreshnessStatus.STALE, FreshnessStatus.UNKNOWN}
            else FreshnessStatus.MIXED
        )
    elif freshnesses == {FreshnessStatus.FRESH}:
        freshness = FreshnessStatus.FRESH
    elif FreshnessStatus.FRESH in freshnesses:
        freshness = FreshnessStatus.MIXED
    else:
        freshness = FreshnessStatus.UNKNOWN
    return overall, freshness
