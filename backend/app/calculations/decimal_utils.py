"""Strict Decimal conversion and rounding rules."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MONEY_QUANTUM = Decimal("0.0001")
RATIO_QUANTUM = Decimal("0.00000001")


def as_decimal(value: Decimal | int | str) -> Decimal:
    """Convert exact inputs while deliberately rejecting binary floats."""
    if isinstance(value, (bool, float)):
        raise TypeError("Financial calculations do not accept bool or float")
    try:
        result = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
    if not result.is_finite():
        raise ValueError("Financial values must be finite")
    return result


def money(value: Decimal | int | str) -> Decimal:
    return as_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def ratio(value: Decimal | int | str) -> Decimal:
    return as_decimal(value).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def require_non_negative(value: Decimal, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must not be negative")
