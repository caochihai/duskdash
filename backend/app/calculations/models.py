"""Typed, persistence-friendly deterministic calculation outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class CalculationResult:
    calculation_type: str
    calculation_version: str
    inputs: dict[str, str]
    formula: str
    result_value: Decimal | None
    unit: str | None
    result_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RepaymentInstallment:
    installment_number: int
    opening_principal: Decimal
    principal_due: Decimal
    interest_due: Decimal
    total_due: Decimal
    closing_principal: Decimal

