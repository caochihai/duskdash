"""Customer and account API contracts."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.common import APIModel, DecimalString


class CustomerResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID | None = None
    customer_id: UUID | None = None
    party_id: UUID
    customer_number: str
    display_name: str | None = None
    full_name: str | None = None
    customer_segment: str | None = None
    home_branch_id: UUID
    relationship_manager_id: UUID | None = None
    kyc_status: str
    risk_rating: str | None = None
    status: str
    updated_at: datetime
    version: int = Field(ge=1)


class AccountResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    account_id: UUID
    account_number_masked: str
    account_type: str
    currency: str
    status: str
    current_balance: DecimalString | None = None
    balance_as_of: datetime | None = None


class CustomerOverviewResponse(CustomerResponse):
    date_of_birth: date | None = None
    employment: list[dict[str, object]] = []
    income_sources: list[dict[str, object]] = []
    kyc_assessments: list[dict[str, object]] = []


class CustomerAssignmentClaimRequest(APIModel):
    expected_version: int = Field(ge=1)


class CustomerAssignmentLeaseRequest(APIModel):
    assignment_version: int = Field(ge=1)
    lease_token: str = Field(min_length=32, max_length=256, repr=False)


class CustomerAssignmentTakeoverRequest(APIModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500, pattern=r".*\S.*")


class CustomerAssignmentLeaseResponse(APIModel):
    customer_id: UUID
    assigned_employee_id: UUID
    assignment_version: int = Field(ge=1)
    lease_token: str = Field(min_length=32, max_length=256, repr=False)
    lease_ttl_seconds: int = Field(ge=1)
    lease_expires_at: datetime


class CustomerAssignmentHeartbeatResponse(APIModel):
    customer_id: UUID
    assigned_employee_id: UUID
    assignment_version: int = Field(ge=1)
    lease_ttl_seconds: int = Field(ge=1)
    lease_expires_at: datetime


class CustomerAssignmentReleaseResponse(APIModel):
    customer_id: UUID
    released_by_employee_id: UUID
    assignment_version: int = Field(ge=1)
    released: bool
