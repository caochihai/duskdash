"""Synthetic happy-path adapters for local demonstrations only.

The values in this module are deliberately fake.  They exercise the agent's
contracts, provenance handling, policy gate, and deterministic rule pipeline;
they are not examples of SHB policy or a production financial calculator.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from .models import (
    CalculationContext,
    CollateralPolicyMode,
    CollateralSnapshotData,
    CollateralSnapshotResult,
    CoveragePeriod,
    CreditFacilitiesData,
    CreditFacilitiesResult,
    CreditPolicyData,
    CreditPolicyResult,
    CreditTaskInputV1,
    Customer360Data,
    Customer360Result,
    FacilityRecord,
    FinancialMetricsData,
    FinancialMetricsResult,
    FinancialStatement,
    FinancialStatementsData,
    FinancialStatementsResult,
    MetricValue,
    PolicyClause,
    PolicyStatus,
    PolicyThresholds,
    RepaymentHistoryData,
    RepaymentHistoryResult,
    ToolStatus,
    TransactionSummaryData,
    TransactionSummaryResult,
)
from .rules import MANDATORY_METRICS


_DEMO_WARNING = "Synthetic demo fixture; do not use this value or source in production."


def _metric(
    current: Decimal | str,
    prior: Decimal | str,
    *,
    unit: str,
    formula: str,
    input_references: list[str],
) -> MetricValue:
    """Build one deterministic metric fixture with an explicit change."""

    current_value = Decimal(current)
    prior_value = Decimal(prior)
    return MetricValue(
        current=current_value,
        prior=prior_value,
        change=current_value - prior_value,
        unit=unit,
        formula=formula,
        input_references=input_references,
    )


class DemoCreditTools:
    """Implement the eight ``CreditTools`` calls with synthetic happy-path data."""

    @staticmethod
    def _provenance(
        task: CreditTaskInputV1,
        tool_name: str,
        *,
        coverage_period: CoveragePeriod | None = None,
    ) -> dict[str, object]:
        identity = uuid5(
            NAMESPACE_URL,
            f"shb-credit-agent-demo:{task.task_id}:{task.as_of_date.isoformat()}:{tool_name}",
        )
        return {
            "task_id": task.task_id,
            "case_id": task.case_id,
            "customer_id": task.customer_id,
            "tool_name": tool_name,
            "tool_run_id": str(identity),
            "status": ToolStatus.OK,
            "source_system": "synthetic_demo_store",
            "source_reference": f"demo://fixtures/{tool_name}/{identity.hex[:16]}",
            "as_of_date": task.as_of_date,
            "retrieved_at": datetime.combine(
                task.as_of_date,
                time(hour=12),
                tzinfo=timezone.utc,
            ),
            "coverage_period": coverage_period,
            "warnings": [_DEMO_WARNING],
        }

    async def get_customer_360(self, task: CreditTaskInputV1) -> Customer360Result:
        outstanding = task.credit_request.current_limit * Decimal("0.75")
        data = Customer360Data(
            years_with_bank=Decimal("6.5"),
            segment="SME",
            internal_rating="A-",
            rating_as_of=task.as_of_date,
            total_outstanding=outstanding,
            average_deposit_balance=task.credit_request.requested_limit * Decimal("0.20"),
            currency=task.credit_request.currency,
            relationship_status="ACTIVE_GOOD_STANDING",
        )
        return Customer360Result(
            **self._provenance(task, "get_customer_360"),
            data=data,
        )

    async def get_credit_facilities(
        self, task: CreditTaskInputV1
    ) -> CreditFacilitiesResult:
        approved_limit = task.credit_request.current_limit
        outstanding = approved_limit * Decimal("0.75")
        data = CreditFacilitiesData(
            approved_limit=approved_limit,
            outstanding=outstanding,
            utilization_ratio=Decimal("0.75"),
            currency=task.credit_request.currency,
            ledger_as_of=task.as_of_date,
            facilities=[
                FacilityRecord(
                    facility_id="demo-facility-001",
                    product_code=task.credit_request.product_code,
                    approved_limit=approved_limit,
                    outstanding=outstanding,
                    utilization_ratio=Decimal("0.75"),
                    currency=task.credit_request.currency,
                )
            ],
        )
        return CreditFacilitiesResult(
            **self._provenance(task, "get_credit_facilities"),
            data=data,
        )

    async def get_repayment_history(
        self, task: CreditTaskInputV1
    ) -> RepaymentHistoryResult:
        coverage = CoveragePeriod(
            start_date=task.as_of_date - timedelta(days=364),
            end_date=task.as_of_date,
        )
        data = RepaymentHistoryData(
            lookback_months=12,
            on_time_payment_count=12,
            late_payment_count=0,
            max_days_past_due=0,
            current_days_past_due=0,
            restructured_debt=False,
            coverage_period=coverage,
        )
        return RepaymentHistoryResult(
            **self._provenance(
                task,
                "get_repayment_history",
                coverage_period=coverage,
            ),
            data=data,
        )

    async def get_transaction_summary(
        self, task: CreditTaskInputV1
    ) -> TransactionSummaryResult:
        coverage = CoveragePeriod(
            start_date=task.as_of_date - timedelta(days=364),
            end_date=task.as_of_date,
        )
        basis = max(task.credit_request.requested_limit, Decimal("1000000000"))
        data = TransactionSummaryData(
            average_monthly_inflow=basis * Decimal("0.3266666667"),
            average_monthly_outflow=basis * Decimal("0.255"),
            inflow_volatility=Decimal("0.08"),
            largest_counterparty_share=Decimal("0.18"),
            related_party_flow=False,
            coverage_months=12,
            coverage_period=coverage,
            currency=task.credit_request.currency,
        )
        return TransactionSummaryResult(
            **self._provenance(
                task,
                "get_transaction_summary",
                coverage_period=coverage,
            ),
            data=data,
        )

    async def get_financial_statements(
        self, task: CreditTaskInputV1
    ) -> FinancialStatementsResult:
        basis = max(task.credit_request.requested_limit, Decimal("1000000000"))
        current_end = task.as_of_date - timedelta(days=30)
        current_start = current_end - timedelta(days=364)
        prior_end = current_start - timedelta(days=1)
        prior_start = prior_end - timedelta(days=364)
        current = FinancialStatement(
            statement_id=f"demo-fs-current-{current_end.isoformat()}",
            period_start=current_start,
            period_end=current_end,
            currency=task.credit_request.currency,
            audited=True,
            revenue=basis * Decimal("4.00"),
            gross_profit=basis * Decimal("1.20"),
            ebitda=basis * Decimal("0.60"),
            net_profit=basis * Decimal("0.36"),
            current_assets=basis * Decimal("2.70"),
            inventory=basis * Decimal("0.75"),
            cash=basis * Decimal("0.45"),
            current_liabilities=basis * Decimal("1.50"),
            total_debt=basis * Decimal("1.80"),
            equity=basis * Decimal("1.50"),
            interest_expense=basis * Decimal("0.12"),
            debt_service=basis * Decimal("0.28125"),
            operating_cash_flow=basis * Decimal("0.45"),
            capital_expenditure=basis * Decimal("0.10"),
            receivables=basis * Decimal("0.65"),
            payables=basis * Decimal("0.55"),
        )
        prior = FinancialStatement(
            statement_id=f"demo-fs-prior-{prior_end.isoformat()}",
            period_start=prior_start,
            period_end=prior_end,
            currency=task.credit_request.currency,
            audited=True,
            revenue=basis * Decimal("3.6363636364"),
            gross_profit=basis * Decimal("1.0545454545"),
            ebitda=basis * Decimal("0.5405405405"),
            net_profit=basis * Decimal("0.3214285714"),
            current_assets=basis * Decimal("2.50"),
            inventory=basis * Decimal("0.7142857143"),
            cash=basis * Decimal("0.40"),
            current_liabilities=basis * Decimal("1.47"),
            total_debt=basis * Decimal("1.75"),
            equity=basis * Decimal("1.46"),
            interest_expense=basis * Decimal("0.125"),
            debt_service=basis * Decimal("0.2857142857"),
            operating_cash_flow=basis * Decimal("0.40"),
            capital_expenditure=basis * Decimal("0.10"),
            receivables=basis * Decimal("0.6018518519"),
            payables=basis * Decimal("0.52"),
        )
        coverage = CoveragePeriod(start_date=prior_start, end_date=current_end)
        return FinancialStatementsResult(
            **self._provenance(
                task,
                "get_financial_statements",
                coverage_period=coverage,
            ),
            data=FinancialStatementsData(current=current, prior=prior),
        )

    async def calculate_financial_metrics(
        self,
        task: CreditTaskInputV1,
        statements: FinancialStatementsResult,
        context: CalculationContext,
    ) -> FinancialMetricsResult:
        """Return a deterministic fixture, not production-grade calculations."""

        current_statement = (
            statements.data.current
            if statements.data is not None and statements.data.current is not None
            else None
        )
        prior_statement = (
            statements.data.prior
            if statements.data is not None and statements.data.prior is not None
            else None
        )
        current_ref = (
            current_statement.statement_id if current_statement else "demo-fs-current"
        )
        prior_ref = prior_statement.statement_id if prior_statement else "demo-fs-prior"
        statement_refs = [current_ref, prior_ref]
        basis = max(context.requested_limit, Decimal("1000000000"))

        metrics = {
            "revenue_growth": _metric(
                "0.10",
                "0.08",
                unit="ratio",
                formula="(revenue_current - revenue_prior) / revenue_prior",
                input_references=statement_refs,
            ),
            "profit_growth": _metric(
                "0.12",
                "0.10",
                unit="ratio",
                formula="(net_profit_current - net_profit_prior) / net_profit_prior",
                input_references=statement_refs,
            ),
            "ebitda_growth": _metric(
                "0.11",
                "0.09",
                unit="ratio",
                formula="(ebitda_current - ebitda_prior) / ebitda_prior",
                input_references=statement_refs,
            ),
            "gross_margin": _metric(
                "0.30",
                "0.29",
                unit="ratio",
                formula="gross_profit / revenue",
                input_references=statement_refs,
            ),
            "ebitda_margin": _metric(
                "0.15",
                "0.1486",
                unit="ratio",
                formula="ebitda / revenue",
                input_references=statement_refs,
            ),
            "current_ratio": _metric(
                "1.80",
                "1.70",
                unit="ratio",
                formula="current_assets / current_liabilities",
                input_references=statement_refs,
            ),
            "quick_ratio": _metric(
                "1.30",
                "1.21",
                unit="ratio",
                formula="(current_assets - inventory) / current_liabilities",
                input_references=statement_refs,
            ),
            "debt_to_equity": _metric(
                "1.20",
                "1.1986",
                unit="ratio",
                formula="total_debt / equity",
                input_references=statement_refs,
            ),
            "debt_to_ebitda": _metric(
                "3.00",
                "3.2375",
                unit="times",
                formula="total_debt / ebitda",
                input_references=statement_refs,
            ),
            "dscr": _metric(
                "1.60",
                "1.40",
                unit="times",
                formula="operating_cash_flow / debt_service",
                input_references=statement_refs,
            ),
            "interest_coverage": _metric(
                "5.00",
                "4.3243",
                unit="times",
                formula="ebitda / interest_expense",
                input_references=statement_refs,
            ),
            "receivable_days": _metric(
                "59.31",
                "60.41",
                unit="days",
                formula="receivables / revenue * 365",
                input_references=statement_refs,
            ),
            "inventory_days": _metric(
                "97.77",
                "101.04",
                unit="days",
                formula="inventory / cost_of_goods_sold * 365",
                input_references=statement_refs,
            ),
            "payable_days": _metric(
                "71.70",
                "73.54",
                unit="days",
                formula="payables / cost_of_goods_sold * 365",
                input_references=statement_refs,
            ),
            "operating_cash_flow": _metric(
                basis * Decimal("0.45"),
                basis * Decimal("0.40"),
                unit=task.credit_request.currency,
                formula="operating_cash_flow",
                input_references=statement_refs,
            ),
            "free_cash_flow": _metric(
                basis * Decimal("0.35"),
                basis * Decimal("0.30"),
                unit=task.credit_request.currency,
                formula="operating_cash_flow - capital_expenditure",
                input_references=statement_refs,
            ),
            "revenue_transaction_variance_ratio": _metric(
                "0.02",
                "0.03",
                unit="ratio",
                formula="abs(revenue - annualized_transaction_inflow) / revenue",
                input_references=statement_refs + ["demo-transaction-summary"],
            ),
            "receivables_growth": _metric(
                "0.08",
                "0.06",
                unit="ratio",
                formula="(receivables_current - receivables_prior) / receivables_prior",
                input_references=statement_refs,
            ),
            "inventory_growth": _metric(
                "0.05",
                "0.04",
                unit="ratio",
                formula="(inventory_current - inventory_prior) / inventory_prior",
                input_references=statement_refs,
            ),
        }
        missing_metrics = MANDATORY_METRICS - set(metrics)
        if missing_metrics:
            raise RuntimeError(
                "Demo metric fixture is incomplete: " + ", ".join(sorted(missing_metrics))
            )

        coverage = None
        if current_statement is not None and prior_statement is not None:
            coverage = CoveragePeriod(
                start_date=prior_statement.period_start,
                end_date=current_statement.period_end,
            )
        return FinancialMetricsResult(
            **self._provenance(
                task,
                "calculate_financial_metrics",
                coverage_period=coverage,
            ),
            data=FinancialMetricsData(
                formula_version="demo-fixture-v1-not-for-production",
                metrics=metrics,
                missing_inputs=[],
                non_computable_metrics=[],
            ),
        )

    async def get_collateral_snapshot(
        self, task: CreditTaskInputV1
    ) -> CollateralSnapshotResult:
        requested_limit = task.credit_request.requested_limit
        data = CollateralSnapshotData(
            collateral_ids=["demo-collateral-001"],
            appraised_value=requested_limit * Decimal("1.80"),
            eligible_value=requested_limit * Decimal("1.50"),
            valuation_date=task.as_of_date - timedelta(days=30),
            coverage_ratio=Decimal("1.50"),
            coverage_denominator=requested_limit,
            coverage_basis="requested_limit",
            valuation_status="CURRENT_DEMO_VALUATION",
            currency=task.credit_request.currency,
        )
        return CollateralSnapshotResult(
            **self._provenance(task, "get_collateral_snapshot"),
            data=data,
        )

    async def retrieve_credit_policy(
        self, task: CreditTaskInputV1
    ) -> CreditPolicyResult:
        data = CreditPolicyData(
            document_id="DEMO-CREDIT-POLICY-NOT-FOR-PRODUCTION",
            version="demo-v1",
            title="Synthetic SME Credit Policy Placeholder",
            status=PolicyStatus.ACTIVE,
            effective_from=task.as_of_date,
            effective_to=None,
            clauses=[
                PolicyClause(
                    section="DEMO-1-SCOPE",
                    content=(
                        "Synthetic policy placeholder for exercising the local Credit Agent "
                        "happy path; it is not an SHB lending rule."
                    ),
                    claim_ids={"claim-policy"},
                ),
                PolicyClause(
                    section="DEMO-2-THRESHOLDS",
                    content=(
                        "All numeric values in this response are test fixtures and must be "
                        "replaced by an active, versioned production policy adapter."
                    ),
                    claim_ids={"claim-policy"},
                ),
            ],
            thresholds=PolicyThresholds(
                repayment_min_coverage_months=12,
                transaction_min_coverage_months=12,
                max_internal_rating_age_days=365,
                max_financial_statement_age_days=180,
                max_collateral_valuation_age_days=180,
                outstanding_conflict_tolerance_ratio=Decimal("0.05"),
                revenue_transaction_mismatch_threshold=Decimal("0.20"),
                receivables_growth_threshold=Decimal("0.25"),
                inventory_growth_threshold=Decimal("0.25"),
                recent_delinquency_days=30,
                maximum_late_payment_count=3,
                maximum_inflow_volatility=Decimal("0.50"),
                minimum_inflow_outflow_ratio=Decimal("1.00"),
                low_limit_utilization_threshold=Decimal("0.50"),
                high_customer_concentration_threshold=Decimal("0.35"),
                minimum_dscr=Decimal("1.20"),
                maximum_debt_to_equity=Decimal("2.50"),
                minimum_interest_coverage=Decimal("2.00"),
                minimum_collateral_coverage=Decimal("1.20"),
                collateral_coverage_tolerance_ratio=Decimal("0.05"),
                maximum_tenor_months=36,
                maximum_requested_limit=Decimal("1000000000000"),
            ),
            applicable_task_types={
                "CREDIT_RENEWAL_REVIEW",
                "CREDIT_LIMIT_REVIEW",
            },
            applicable_product_codes={task.credit_request.product_code},
            applicable_currencies={task.credit_request.currency},
            applicable_segments={"SME"},
            allowed_internal_ratings={"A-"},
            allowed_relationship_statuses={"ACTIVE_GOOD_STANDING"},
            allowed_collateral_valuation_statuses={
                "CURRENT_DEMO_VALUATION"
            },
            allowed_collateral_coverage_bases={"requested_limit"},
            require_audited_financial_statements=True,
            collateral_mode=(
                CollateralPolicyMode.REQUIRED
                if task.credit_request.collateral_required
                else CollateralPolicyMode.OPTIONAL
            ),
            required_metrics=set(MANDATORY_METRICS),
            not_recommended_flag_codes=set(),
            condition_flag_codes=set(),
            not_recommended_metric_names=set(),
            condition_metric_names=set(),
            severity_by_flag={},
            placeholder_data=True,
        )
        provenance = self._provenance(task, "retrieve_credit_policy")
        provenance["warnings"] = [
            "Active only as a synthetic demo placeholder; no production policy authority."
        ]
        return CreditPolicyResult(**provenance, data=data)
