from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest


# Keep `pytest` runnable from a source checkout without requiring an editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from credit_agent.models import (  # noqa: E402
    CollateralSnapshotData,
    CollateralSnapshotResult,
    CollateralPolicyMode,
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
    RiskCode,
    RiskSeverity,
    ToolEnvelope,
    ToolStatus,
    TransactionSummaryData,
    TransactionSummaryResult,
)
from credit_agent.rules import MANDATORY_METRICS  # noqa: E402


AS_OF_DATE = date(2026, 6, 30)
RETRIEVED_AT = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)
ALL_SCOPES = {
    "customer:read",
    "credit:read",
    "transactions:read",
    "financials:read",
    "collateral:read",
    "policy:read",
}
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


def build_task() -> CreditTaskInputV1:
    return CreditTaskInputV1.model_validate(
        {
            "task_id": "task-credit-001",
            "case_id": "case-sme-001",
            "task_type": "CREDIT_RENEWAL_REVIEW",
            "customer_id": "customer-001",
            "credit_request": {
                "request_type": "RENEWAL",
                "product_code": "SME-WC",
                "current_limit": "1000000",
                "requested_limit": "1000000",
                "requested_tenor_months": 12,
                "currency": "VND",
                "purpose": "Renew working-capital facility",
                "collateral_required": True,
            },
            "as_of_date": AS_OF_DATE,
            "permissions": {"allowed_scopes": ALL_SCOPES},
        }
    )


def _envelope_fields(name: str, source_system: str) -> dict[str, Any]:
    return {
        "task_id": "task-credit-001",
        "case_id": "case-sme-001",
        "customer_id": "customer-001",
        "tool_name": name,
        "tool_run_id": f"run-{name}",
        "status": ToolStatus.OK,
        "source_system": source_system,
        "source_reference": f"ref-{name}",
        "as_of_date": AS_OF_DATE,
        "retrieved_at": RETRIEVED_AT,
    }


def _statement(
    *,
    statement_id: str,
    period_start: date,
    period_end: date,
    revenue: str,
    net_profit: str,
    operating_cash_flow: str,
) -> FinancialStatement:
    return FinancialStatement(
        statement_id=statement_id,
        period_start=period_start,
        period_end=period_end,
        currency="VND",
        audited=True,
        revenue=Decimal(revenue),
        gross_profit=Decimal("1200000"),
        ebitda=Decimal("700000"),
        net_profit=Decimal(net_profit),
        current_assets=Decimal("2000000"),
        inventory=Decimal("400000"),
        cash=Decimal("500000"),
        current_liabilities=Decimal("800000"),
        total_debt=Decimal("1000000"),
        equity=Decimal("1200000"),
        interest_expense=Decimal("100000"),
        debt_service=Decimal("400000"),
        operating_cash_flow=Decimal(operating_cash_flow),
        capital_expenditure=Decimal("100000"),
        receivables=Decimal("600000"),
        payables=Decimal("300000"),
    )


def _metrics() -> dict[str, MetricValue]:
    safe_values = {name: Decimal("0.10") for name in MANDATORY_METRICS}
    safe_values.update(
        {
            "revenue_transaction_variance_ratio": Decimal("0.05"),
            "receivables_growth": Decimal("0.05"),
            "inventory_growth": Decimal("0.05"),
            "dscr": Decimal("1.50"),
            "debt_to_equity": Decimal("1.00"),
            "interest_coverage": Decimal("4.00"),
            "operating_cash_flow": Decimal("500000"),
            "free_cash_flow": Decimal("400000"),
        }
    )
    return {
        name: MetricValue(
            current=value,
            prior=value,
            change=Decimal("0"),
            unit="ratio" if name not in {"operating_cash_flow", "free_cash_flow"} else "VND",
            formula=f"fixture:{name}",
            input_references=["ref-financial-statements"],
        )
        for name, value in safe_values.items()
    }


def build_outputs() -> dict[str, ToolEnvelope[Any]]:
    coverage = CoveragePeriod(start_date=date(2025, 7, 1), end_date=AS_OF_DATE)
    current = _statement(
        statement_id="fs-current",
        period_start=date(2025, 7, 1),
        period_end=AS_OF_DATE,
        revenue="3600000",
        net_profit="300000",
        operating_cash_flow="500000",
    )
    prior = _statement(
        statement_id="fs-prior",
        period_start=date(2024, 7, 1),
        period_end=date(2025, 6, 30),
        revenue="3300000",
        net_profit="250000",
        operating_cash_flow="420000",
    )
    policy = CreditPolicyData(
        document_id="policy-sme-renewal",
        version="2026.1",
        title="SME renewal policy",
        status=PolicyStatus.ACTIVE,
        effective_from=date(2026, 1, 1),
        clauses=[
            PolicyClause(
                section="renewal.eligibility",
                content="Typed fixture clause",
                claim_ids={"claim-policy"},
            )
        ],
        thresholds=PolicyThresholds(
            repayment_min_coverage_months=12,
            transaction_min_coverage_months=12,
            max_internal_rating_age_days=365,
            max_financial_statement_age_days=365,
            max_collateral_valuation_age_days=90,
            outstanding_conflict_tolerance_ratio=Decimal("0.05"),
            revenue_transaction_mismatch_threshold=Decimal("0.20"),
            receivables_growth_threshold=Decimal("0.30"),
            inventory_growth_threshold=Decimal("0.30"),
            recent_delinquency_days=30,
            maximum_late_payment_count=3,
            maximum_inflow_volatility=Decimal("0.50"),
            minimum_inflow_outflow_ratio=Decimal("1.00"),
            low_limit_utilization_threshold=Decimal("0.50"),
            high_customer_concentration_threshold=Decimal("0.50"),
            minimum_dscr=Decimal("1.20"),
            maximum_debt_to_equity=Decimal("2.00"),
            minimum_interest_coverage=Decimal("2.00"),
            minimum_collateral_coverage=Decimal("1.00"),
            collateral_coverage_tolerance_ratio=Decimal("0.05"),
            maximum_tenor_months=24,
            maximum_requested_limit=Decimal("5000000"),
        ),
        applicable_task_types={"CREDIT_RENEWAL_REVIEW", "CREDIT_LIMIT_REVIEW"},
        applicable_product_codes={"SME-WC"},
        applicable_currencies={"VND"},
        applicable_segments={"SME"},
        allowed_internal_ratings={"A", "B"},
        allowed_relationship_statuses={"ACTIVE"},
        allowed_collateral_valuation_statuses={"VALID"},
        allowed_collateral_coverage_bases={"requested_limit"},
        require_audited_financial_statements=True,
        collateral_mode=CollateralPolicyMode.REQUIRED,
        condition_flag_codes={RiskCode.LOW_LIMIT_UTILIZATION},
        severity_by_flag={
            code: (
                RiskSeverity.HIGH
                if code
                in {
                    RiskCode.FINANCIAL_DATA_CONFLICT,
                    RiskCode.MISSING_LATEST_FINANCIALS,
                    RiskCode.RELATED_PARTY_FLOW,
                }
                else RiskSeverity.MEDIUM
            )
            for code in RiskCode
        },
    )
    return {
        "retrieve_credit_policy": CreditPolicyResult(
            **_envelope_fields("retrieve_credit_policy", "policy_repository"), data=policy
        ),
        "get_customer_360": Customer360Result(
            **_envelope_fields("get_customer_360", "customer_360"),
            data=Customer360Data(
                years_with_bank=Decimal("6.5"),
                segment="SME",
                internal_rating="A",
                rating_as_of=AS_OF_DATE,
                total_outstanding=Decimal("800000"),
                average_deposit_balance=Decimal("250000"),
                currency="VND",
                relationship_status="ACTIVE",
            ),
        ),
        "get_credit_facilities": CreditFacilitiesResult(
            **_envelope_fields("get_credit_facilities", "loan_ledger"),
            data=CreditFacilitiesData(
                approved_limit=Decimal("1000000"),
                outstanding=Decimal("800000"),
                utilization_ratio=Decimal("0.80"),
                currency="VND",
                ledger_as_of=AS_OF_DATE,
                facilities=[
                    FacilityRecord(
                        facility_id="facility-001",
                        product_code="SME-WC",
                        approved_limit=Decimal("1000000"),
                        outstanding=Decimal("800000"),
                        utilization_ratio=Decimal("0.80"),
                        currency="VND",
                        maturity_date=date(2026, 7, 31),
                    )
                ],
            ),
        ),
        "get_repayment_history": RepaymentHistoryResult(
            **_envelope_fields("get_repayment_history", "loan_ledger"),
            coverage_period=coverage,
            data=RepaymentHistoryData(
                lookback_months=12,
                on_time_payment_count=12,
                late_payment_count=0,
                max_days_past_due=0,
                current_days_past_due=0,
                restructured_debt=False,
                coverage_period=coverage,
            ),
        ),
        "get_transaction_summary": TransactionSummaryResult(
            **_envelope_fields("get_transaction_summary", "transaction_warehouse"),
            coverage_period=coverage,
            data=TransactionSummaryData(
                average_monthly_inflow=Decimal("300000"),
                average_monthly_outflow=Decimal("220000"),
                inflow_volatility=Decimal("0.10"),
                largest_counterparty_share=Decimal("0.20"),
                related_party_flow=False,
                coverage_months=12,
                coverage_period=coverage,
                currency="VND",
            ),
        ),
        "get_financial_statements": FinancialStatementsResult(
            **_envelope_fields("get_financial_statements", "financial_statement_store"),
            data=FinancialStatementsData(current=current, prior=prior),
        ),
        "calculate_financial_metrics": FinancialMetricsResult(
            **_envelope_fields("calculate_financial_metrics", "deterministic_calculator"),
            data=FinancialMetricsData(formula_version="fixture-v1", metrics=_metrics()),
        ),
        "get_collateral_snapshot": CollateralSnapshotResult(
            **_envelope_fields("get_collateral_snapshot", "collateral_registry"),
            data=CollateralSnapshotData(
                collateral_ids=["collateral-001"],
                appraised_value=Decimal("1700000"),
                eligible_value=Decimal("1500000"),
                valuation_date=date(2026, 6, 1),
                coverage_ratio=Decimal("1.50"),
                coverage_denominator=Decimal("1000000"),
                coverage_basis="requested_limit",
                valuation_status="VALID",
                currency="VND",
            ),
        ),
    }


class FakeCreditTools:
    """Deterministic in-memory implementation of all eight CreditTools calls."""

    def __init__(self, outputs: dict[str, ToolEnvelope[Any]]) -> None:
        self.outputs = outputs
        self.calls: list[str] = []
        self.fail_if_called: set[str] = set()

    async def _return(self, name: str) -> ToolEnvelope[Any]:
        self.calls.append(name)
        if name in self.fail_if_called:
            raise AssertionError(f"{name} must not be called in this scenario")
        return self.outputs[name]

    async def retrieve_credit_policy(self, task: CreditTaskInputV1) -> CreditPolicyResult:
        del task
        return await self._return("retrieve_credit_policy")  # type: ignore[return-value]

    async def get_customer_360(self, task: CreditTaskInputV1) -> Customer360Result:
        del task
        return await self._return("get_customer_360")  # type: ignore[return-value]

    async def get_credit_facilities(self, task: CreditTaskInputV1) -> CreditFacilitiesResult:
        del task
        return await self._return("get_credit_facilities")  # type: ignore[return-value]

    async def get_repayment_history(self, task: CreditTaskInputV1) -> RepaymentHistoryResult:
        del task
        return await self._return("get_repayment_history")  # type: ignore[return-value]

    async def get_transaction_summary(self, task: CreditTaskInputV1) -> TransactionSummaryResult:
        del task
        return await self._return("get_transaction_summary")  # type: ignore[return-value]

    async def get_financial_statements(self, task: CreditTaskInputV1) -> FinancialStatementsResult:
        del task
        return await self._return("get_financial_statements")  # type: ignore[return-value]

    async def calculate_financial_metrics(
        self,
        task: CreditTaskInputV1,
        statements: FinancialStatementsResult,
        context: Any,
    ) -> FinancialMetricsResult:
        del task, statements, context
        return await self._return("calculate_financial_metrics")  # type: ignore[return-value]

    async def get_collateral_snapshot(self, task: CreditTaskInputV1) -> CollateralSnapshotResult:
        del task
        return await self._return("get_collateral_snapshot")  # type: ignore[return-value]

    def update_data(self, tool_name: str, **changes: Any) -> None:
        envelope = self.outputs[tool_name]
        assert envelope.data is not None
        self.outputs[tool_name] = envelope.model_copy(
            update={"data": envelope.data.model_copy(update=changes)}
        )

    def update_policy_thresholds(self, **changes: Any) -> None:
        envelope = self.outputs["retrieve_credit_policy"]
        assert isinstance(envelope.data, CreditPolicyData)
        policy = envelope.data.model_copy(
            update={"thresholds": envelope.data.thresholds.model_copy(update=changes)}
        )
        self.outputs["retrieve_credit_policy"] = envelope.model_copy(update={"data": policy})

    def set_tool_error(self, tool_name: str, message: str = "fixture failure") -> None:
        envelope = self.outputs[tool_name]
        self.outputs[tool_name] = envelope.model_copy(
            update={"status": ToolStatus.ERROR, "data": None, "error": message}
        )


@dataclass
class CreditCase:
    task: CreditTaskInputV1
    tools: FakeCreditTools


@pytest.fixture
def credit_case_factory():
    def make() -> CreditCase:
        return CreditCase(task=build_task(), tools=FakeCreditTools(build_outputs()))

    return make
