"""Object adapter implementing the application service calculator protocol."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.calculations.affordability import dscr, dti, ltv
from app.calculations.income import average_income
from app.calculations.repayment import annuity_payment


class CalculationEngine:
    def average_income(self, values: Sequence[Decimal]) -> Decimal:
        return average_income(values)

    def annuity_payment(
        self,
        principal: Decimal,
        annual_rate: Decimal,
        term_months: int,
    ) -> Decimal:
        return annuity_payment(principal, annual_rate, term_months)

    def dti(
        self,
        obligations: Decimal,
        projected_payment: Decimal,
        income: Decimal,
    ) -> Decimal:
        return dti(obligations, projected_payment, income)

    def dscr(
        self,
        income: Decimal,
        obligations: Decimal,
        projected_payment: Decimal,
    ) -> Decimal:
        return dscr(income, obligations, projected_payment)

    def ltv(self, amount: Decimal, collateral_value: Decimal) -> Decimal:
        return ltv(amount, collateral_value)

