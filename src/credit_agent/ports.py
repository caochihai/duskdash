"""Framework-neutral ports implemented by the host application."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import (
    AuditEvent,
    CalculationContext,
    CollateralSnapshotResult,
    CreditFacilitiesResult,
    CreditPolicyResult,
    CreditTaskInputV1,
    Customer360Result,
    FinancialMetricsResult,
    FinancialStatementsResult,
    RepaymentHistoryResult,
    TransactionSummaryResult,
)


class CreditTools(Protocol):
    async def get_customer_360(self, task: CreditTaskInputV1) -> Customer360Result: ...

    async def get_credit_facilities(self, task: CreditTaskInputV1) -> CreditFacilitiesResult: ...

    async def get_repayment_history(self, task: CreditTaskInputV1) -> RepaymentHistoryResult: ...

    async def get_transaction_summary(self, task: CreditTaskInputV1) -> TransactionSummaryResult: ...

    async def get_financial_statements(self, task: CreditTaskInputV1) -> FinancialStatementsResult: ...

    async def calculate_financial_metrics(
        self,
        task: CreditTaskInputV1,
        statements: FinancialStatementsResult,
        context: CalculationContext,
    ) -> FinancialMetricsResult: ...

    async def get_collateral_snapshot(self, task: CreditTaskInputV1) -> CollateralSnapshotResult: ...

    async def retrieve_credit_policy(self, task: CreditTaskInputV1) -> CreditPolicyResult: ...


class AuditSink(Protocol):
    durable: bool

    async def emit(self, event: AuditEvent) -> None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...
