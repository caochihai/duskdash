"""Income aggregation and volatility calculations."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from app.calculations.decimal_utils import as_decimal, money, ratio, require_non_negative
from app.calculations.models import CalculationResult

VERSION = "1.0"


def _values(values: Iterable[Decimal | int | str]) -> tuple[Decimal, ...]:
    result = tuple(as_decimal(value) for value in values)
    if not result:
        raise ValueError("At least one income value is required")
    for value in result:
        require_non_negative(value, "income")
    return result


def average_income(values: Iterable[Decimal | int | str]) -> Decimal:
    exact = _values(values)
    return money(sum(exact, Decimal(0)) / len(exact))


def income_volatility(values: Iterable[Decimal | int | str]) -> Decimal:
    """Population coefficient of variation (standard deviation / mean)."""
    exact = _values(values)
    mean = sum(exact, Decimal(0)) / len(exact)
    if mean == 0:
        return Decimal("0.00000000")
    variance = sum(((value - mean) ** 2 for value in exact), Decimal(0)) / len(exact)
    return ratio(variance.sqrt() / mean)


def average_income_calculation(
    values: Iterable[Decimal | int | str],
) -> CalculationResult:
    exact = _values(values)
    result = money(sum(exact, Decimal(0)) / len(exact))
    return CalculationResult(
        calculation_type="AVERAGE_VERIFIED_INCOME",
        calculation_version=VERSION,
        inputs={"values": ",".join(str(value) for value in exact)},
        formula="sum(verified_monthly_income) / observation_count",
        result_value=result,
        unit="CURRENCY_PER_MONTH",
        result_payload={"observation_count": len(exact)},
    )

