"""Loan application and authorized human-decision contracts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.common import APIModel, DecimalString


class LoanCreateRequest(APIModel):
    primary_customer_id: UUID
    product_id: UUID
    requested_amount: DecimalString
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    requested_term_months: int = Field(gt=0)
    loan_purpose: str = Field(min_length=1, max_length=40)
    interest_rate_assumption: DecimalString | None = None
    repayment_method: str | None = Field(default=None, max_length=40)


class LoanUpdateRequest(APIModel):
    requested_amount: DecimalString | None = None
    requested_term_months: int | None = Field(default=None, gt=0)
    loan_purpose: str | None = Field(default=None, max_length=40)
    interest_rate_assumption: DecimalString | None = None
    repayment_method: str | None = Field(default=None, max_length=40)
    status: str | None = None
    assigned_employee_id: UUID | None = None
    version: int = Field(gt=0)


class LoanResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    application_number: str
    primary_customer_id: UUID
    product_id: UUID
    requested_amount: DecimalString
    currency: str
    requested_term_months: int
    loan_purpose: str
    status: str
    version: int


class LoanPartyRequest(APIModel):
    party_id: UUID
    party_role: str


class AnalysisRequest(APIModel):
    objective: str = Field(min_length=1, max_length=2000)


class SubmitLoanRequest(APIModel):
    version: int = Field(gt=0)


class LoanDecisionRequest(APIModel):
    approval_request_id: UUID | None = None
    decision_type: str
    approved_amount: DecimalString | None = None
    approved_term_months: int | None = Field(default=None, gt=0)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = Field(min_length=1, max_length=4000)
    is_override: bool = False
    override_reason: str | None = Field(default=None, max_length=2000)

