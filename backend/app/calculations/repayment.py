"""Deterministic repayment calculations using Decimal only."""

from __future__ import annotations

from decimal import Decimal

from app.calculations.decimal_utils import as_decimal, money, require_non_negative
from app.calculations.models import CalculationResult, RepaymentInstallment

VERSION = "1.0"


def monthly_rate(annual_rate: Decimal | int | str) -> Decimal:
    annual = as_decimal(annual_rate)
    require_non_negative(annual, "annual_rate")
    return annual / Decimal(12)


def annuity_payment(
    principal: Decimal | int | str,
    annual_rate: Decimal | int | str,
    term_months: int,
) -> Decimal:
    amount = as_decimal(principal)
    require_non_negative(amount, "principal")
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    rate = monthly_rate(annual_rate)
    if rate == 0:
        return money(amount / term_months)
    factor = (Decimal(1) + rate) ** term_months
    return money(amount * rate * factor / (factor - Decimal(1)))


def equal_principal_schedule(
    principal: Decimal | int | str,
    annual_rate: Decimal | int | str,
    term_months: int,
) -> tuple[RepaymentInstallment, ...]:
    amount = money(principal)
    require_non_negative(amount, "principal")
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    rate = monthly_rate(annual_rate)
    base_principal = money(amount / term_months)
    outstanding = amount
    schedule: list[RepaymentInstallment] = []
    for number in range(1, term_months + 1):
        principal_due = outstanding if number == term_months else min(base_principal, outstanding)
        interest_due = money(outstanding * rate)
        closing = money(outstanding - principal_due)
        schedule.append(
            RepaymentInstallment(
                installment_number=number,
                opening_principal=outstanding,
                principal_due=principal_due,
                interest_due=interest_due,
                total_due=money(principal_due + interest_due),
                closing_principal=closing,
            )
        )
        outstanding = closing
    return tuple(schedule)


def annuity_schedule(
    principal: Decimal | int | str,
    annual_rate: Decimal | int | str,
    term_months: int,
) -> tuple[RepaymentInstallment, ...]:
    amount = money(principal)
    require_non_negative(amount, "principal")
    payment = annuity_payment(amount, annual_rate, term_months)
    rate = monthly_rate(annual_rate)
    outstanding = amount
    schedule: list[RepaymentInstallment] = []
    for number in range(1, term_months + 1):
        interest_due = money(outstanding * rate)
        principal_due = outstanding if number == term_months else money(payment - interest_due)
        if principal_due < 0:
            raise ValueError("Payment does not cover accrued interest")
        closing = money(outstanding - principal_due)
        total = money(principal_due + interest_due)
        schedule.append(
            RepaymentInstallment(
                installment_number=number,
                opening_principal=outstanding,
                principal_due=principal_due,
                interest_due=interest_due,
                total_due=total,
                closing_principal=closing,
            )
        )
        outstanding = closing
    return tuple(schedule)


def payment_calculation(
    principal: Decimal | int | str,
    annual_rate: Decimal | int | str,
    term_months: int,
    repayment_method: str,
) -> CalculationResult:
    method = repayment_method.upper()
    if method == "ANNUITY":
        result = annuity_payment(principal, annual_rate, term_months)
        formula = "P*r*(1+r)^n/((1+r)^n-1), r=annual_rate/12"
    elif method == "EQUAL_PRINCIPAL":
        result = equal_principal_schedule(principal, annual_rate, term_months)[0].total_due
        formula = "P/n + P*annual_rate/12 (first installment)"
    else:
        raise ValueError("repayment_method must be ANNUITY or EQUAL_PRINCIPAL")
    return CalculationResult(
        calculation_type="PROJECTED_MONTHLY_PAYMENT",
        calculation_version=VERSION,
        inputs={
            "principal": str(as_decimal(principal)),
            "annual_rate": str(as_decimal(annual_rate)),
            "term_months": str(term_months),
            "repayment_method": method,
        },
        formula=formula,
        result_value=result,
        unit="CURRENCY_PER_MONTH",
    )

