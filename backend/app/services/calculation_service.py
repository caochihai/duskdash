"""Persistence facade around deterministic Decimal calculators."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from app.services.access import require_permission
from app.services.protocols import PrincipalLike


class CalculationRepositoryLike(Protocol):
    async def add_record(self, values: Mapping[str, Any]) -> Mapping[str, Any]: ...


class CalculatorLike(Protocol):
    def average_income(self, values: Sequence[Decimal]) -> Decimal: ...

    def annuity_payment(
        self, principal: Decimal, annual_rate: Decimal, term_months: int
    ) -> Decimal: ...

    def dti(self, obligations: Decimal, projected_payment: Decimal, income: Decimal) -> Decimal: ...

    def dscr(self, income: Decimal, obligations: Decimal, projected_payment: Decimal) -> Decimal: ...

    def ltv(self, amount: Decimal, collateral_value: Decimal) -> Decimal: ...


class CalculationService:
    def __init__(
        self, repository: CalculationRepositoryLike, calculator: CalculatorLike
    ) -> None:
        self._repository = repository
        self._calculator = calculator

    async def affordability(
        self,
        principal: PrincipalLike,
        *,
        loan_application_id: UUID,
        analysis_case_id: UUID | None,
        accepted_income_values: Sequence[Decimal],
        existing_obligations: Decimal,
        requested_amount: Decimal,
        annual_rate: Decimal,
        term_months: int,
        eligible_collateral_value: Decimal | None,
        source_references: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:analyze")
        income = self._calculator.average_income(accepted_income_values)
        payment = self._calculator.annuity_payment(requested_amount, annual_rate, term_months)
        dti = self._calculator.dti(existing_obligations, payment, income)
        dscr = self._calculator.dscr(income, existing_obligations, payment)
        ltv = (
            self._calculator.ltv(requested_amount, eligible_collateral_value)
            if eligible_collateral_value and eligible_collateral_value > 0
            else None
        )
        inputs = {
            "accepted_income_values": [str(value) for value in accepted_income_values],
            "existing_obligations": str(existing_obligations),
            "requested_amount": str(requested_amount),
            "annual_rate": str(annual_rate),
            "term_months": term_months,
            "eligible_collateral_value": (
                str(eligible_collateral_value) if eligible_collateral_value is not None else None
            ),
            "source_references": list(source_references),
        }
        result_payload = {
            "accepted_monthly_income": str(income),
            "projected_monthly_payment": str(payment),
            "dti": str(dti),
            "dscr": str(dscr),
            "ltv": str(ltv) if ltv is not None else None,
            "net_disposable_income": str(income - existing_obligations - payment),
        }
        return await self._repository.add_record(
            {
                "loan_application_id": loan_application_id,
                "analysis_case_id": analysis_case_id,
                "calculation_type": "AFFORDABILITY",
                "calculation_version": "1.0",
                "inputs": inputs,
                "formula": "Deterministic annuity payment, DTI, DSCR and LTV; no policy threshold",
                "result_value": dti,
                "result_payload": result_payload,
                "unit": "RATIO",
                "created_by_type": "EMPLOYEE",
                "created_by_id": principal.employee_id,
            }
        )

