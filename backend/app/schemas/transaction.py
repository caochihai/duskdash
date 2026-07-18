"""Transaction query contracts with Decimal money fields."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.common import APIModel, DecimalString


class TransactionResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    transaction_id: UUID
    account_id: UUID
    booking_time: datetime
    value_date: date | None = None
    direction: str
    amount: DecimalString
    currency: str
    transaction_type: str | None = None
    description: str | None = None
    balance_after: DecimalString | None = None
    counterparty_name_masked: str | None = None
    status: str


class TransactionSummaryResponse(APIModel):
    total_inflow: DecimalString
    total_outflow: DecimalString
    salary_inflow: DecimalString
    transaction_count: int
    period_start: datetime | None = None
    period_end: datetime | None = None

