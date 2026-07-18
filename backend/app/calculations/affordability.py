"""Deterministic affordability ratios; policy thresholds live elsewhere."""

from __future__ import annotations

from decimal import Decimal

from app.calculations.decimal_utils import as_decimal, money, ratio, require_non_negative
from app.calculations.models import CalculationResult

VERSION = "1.0"


def dti(
    monthly_obligations: Decimal | int | str,
    projected_payment: Decimal | int | str,
    monthly_accepted_income: Decimal | int | str,
) -> Decimal:
    obligations = as_decimal(monthly_obligations)
    payment = as_decimal(projected_payment)
    income = as_decimal(monthly_accepted_income)
    require_non_negative(obligations, "monthly_obligations")
    require_non_negative(payment, "projected_payment")
    if income <= 0:
        raise ValueError("monthly_accepted_income must be positive")
    return ratio((obligations + payment) / income)


def dscr(
    monthly_accepted_income: Decimal | int | str,
    monthly_obligations: Decimal | int | str,
    projected_payment: Decimal | int | str | None = None,
) -> Decimal:
    income = as_decimal(monthly_accepted_income)
    service = as_decimal(monthly_obligations)
    if projected_payment is not None:
        service += as_decimal(projected_payment)
    require_non_negative(income, "monthly_accepted_income")
    if service <= 0:
        raise ValueError("total monthly debt service must be positive")
    return ratio(income / service)


def ltv(
    loan_amount: Decimal | int | str,
    eligible_collateral_value: Decimal | int | str,
) -> Decimal:
    amount = as_decimal(loan_amount)
    collateral = as_decimal(eligible_collateral_value)
    require_non_negative(amount, "loan_amount")
    if collateral <= 0:
        raise ValueError("eligible_collateral_value must be positive")
    return ratio(amount / collateral)


def net_disposable_income(
    monthly_accepted_income: Decimal | int | str,
    monthly_obligations: Decimal | int | str,
    projected_payment: Decimal | int | str,
) -> Decimal:
    income = as_decimal(monthly_accepted_income)
    obligations = as_decimal(monthly_obligations)
    payment = as_decimal(projected_payment)
    require_non_negative(income, "monthly_accepted_income")
    require_non_negative(obligations, "monthly_obligations")
    require_non_negative(payment, "projected_payment")
    return money(income - obligations - payment)


def stress_interest_rate(
    base_annual_rate: Decimal | int | str,
    shock: Decimal | int | str,
) -> Decimal:
    base = as_decimal(base_annual_rate)
    increment = as_decimal(shock)
    require_non_negative(base, "base_annual_rate")
    require_non_negative(increment, "shock")
    return ratio(base + increment)


def dti_calculation(
    monthly_obligations: Decimal | int | str,
    projected_payment: Decimal | int | str,
    monthly_accepted_income: Decimal | int | str,
) -> CalculationResult:
    result = dti(monthly_obligations, projected_payment, monthly_accepted_income)
    return CalculationResult(
        calculation_type="DTI",
        calculation_version=VERSION,
        inputs={
            "monthly_obligations": str(as_decimal(monthly_obligations)),
            "projected_payment": str(as_decimal(projected_payment)),
            "monthly_accepted_income": str(as_decimal(monthly_accepted_income)),
        },
        formula="(monthly_obligations + projected_payment) / monthly_accepted_income",
        result_value=result,
        unit="RATIO",
    )
