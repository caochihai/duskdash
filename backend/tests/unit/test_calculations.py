from decimal import Decimal

import pytest

from app.calculations import (
    annuity_payment,
    annuity_schedule,
    average_income,
    dscr,
    dti,
    equal_principal_schedule,
    income_volatility,
    ltv,
    net_disposable_income,
)


def test_demo_income_average_is_exact_decimal() -> None:
    values = [Decimal("22000000.0000")] * 12
    assert average_income(values) == Decimal("22000000.0000")
    assert income_volatility(values) == Decimal("0.00000000")


def test_affordability_ratios_and_money_are_deterministic() -> None:
    assert dti("6000000", "14000000", "22000000") == Decimal("0.90909091")
    assert dscr("22000000", "20000000") == Decimal("1.10000000")
    assert ltv("700000000", "1000000000") == Decimal("0.70000000")
    assert net_disposable_income("22000000", "6000000", "14000000") == Decimal("2000000.0000")


def test_equal_principal_schedule_reconciles_to_principal() -> None:
    schedule = equal_principal_schedule("700000000", "0.085", 60)
    assert len(schedule) == 60
    assert sum((item.principal_due for item in schedule), Decimal(0)) == Decimal("700000000.0000")
    assert schedule[-1].closing_principal == Decimal("0.0000")
    assert schedule[0].total_due > schedule[-1].total_due


def test_annuity_schedule_reconciles_and_has_stable_payment() -> None:
    payment = annuity_payment("700000000", "0.085", 60)
    schedule = annuity_schedule("700000000", "0.085", 60)
    assert payment > Decimal("0")
    assert schedule[-1].closing_principal == Decimal("0.0000")
    assert sum((item.principal_due for item in schedule), Decimal(0)) == Decimal("700000000.0000")
    assert all(item.total_due == payment for item in schedule[:-1])


@pytest.mark.parametrize("function", [annuity_payment, equal_principal_schedule])
def test_binary_float_is_rejected(function: object) -> None:
    with pytest.raises(TypeError):
        function(700_000_000.0, "0.085", 60)  # type: ignore[operator]


def test_invalid_denominators_fail_closed() -> None:
    with pytest.raises(ValueError):
        dti("1", "2", "0")
    with pytest.raises(ValueError):
        ltv("1", "0")

