"""Authorized customer, account, and transaction endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import (
    get_customer_assignment_service,
    get_customer_service,
    get_transaction_service,
)
from app.api.v1._utils import page_response, request_uuid
from app.auth.dependencies import require_permissions
from app.auth.principal import CurrentPrincipal
from app.schemas.common import PaginatedResponse
from app.schemas.customer import (
    AccountResponse,
    CustomerAssignmentClaimRequest,
    CustomerAssignmentHeartbeatResponse,
    CustomerAssignmentLeaseRequest,
    CustomerAssignmentLeaseResponse,
    CustomerAssignmentReleaseResponse,
    CustomerAssignmentTakeoverRequest,
    CustomerOverviewResponse,
    CustomerResponse,
)
from app.schemas.document import DocumentResponse
from app.schemas.loan import LoanResponse
from app.schemas.transaction import TransactionResponse, TransactionSummaryResponse
from app.services.customer_assignment_service import CustomerAssignmentService
from app.services.customer_service import CustomerService
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=PaginatedResponse[CustomerResponse])
async def list_customers(
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("customer:search"))],
    service: Annotated[CustomerService, Depends(get_customer_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None, max_length=200),
) -> PaginatedResponse[CustomerResponse]:
    rows, total = await service.list_customers(
        principal, page=page, page_size=page_size, search=search
    )
    return page_response(CustomerResponse, rows, page=page, page_size=page_size, total=total)


@router.post(
    "/{customer_id}/assignment/claim",
    response_model=CustomerAssignmentLeaseResponse,
)
async def claim_customer_assignment(
    customer_id: UUID,
    body: CustomerAssignmentClaimRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("customer:read"))],
    service: Annotated[
        CustomerAssignmentService, Depends(get_customer_assignment_service)
    ],
) -> CustomerAssignmentLeaseResponse:
    result = await service.claim(
        principal,
        customer_id,
        expected_version=body.expected_version,
        request_id=request_uuid(request),
    )
    return CustomerAssignmentLeaseResponse.model_validate(result)


@router.post(
    "/{customer_id}/assignment/heartbeat",
    response_model=CustomerAssignmentHeartbeatResponse,
)
async def heartbeat_customer_assignment(
    customer_id: UUID,
    body: CustomerAssignmentLeaseRequest,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("customer:read"))],
    service: Annotated[
        CustomerAssignmentService, Depends(get_customer_assignment_service)
    ],
) -> CustomerAssignmentHeartbeatResponse:
    result = await service.heartbeat(
        principal,
        customer_id,
        assignment_version=body.assignment_version,
        lease_token=body.lease_token,
    )
    return CustomerAssignmentHeartbeatResponse.model_validate(result)


@router.post(
    "/{customer_id}/assignment/release",
    response_model=CustomerAssignmentReleaseResponse,
)
async def release_customer_assignment(
    customer_id: UUID,
    body: CustomerAssignmentLeaseRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("customer:read"))],
    service: Annotated[
        CustomerAssignmentService, Depends(get_customer_assignment_service)
    ],
) -> CustomerAssignmentReleaseResponse:
    result = await service.release(
        principal,
        customer_id,
        assignment_version=body.assignment_version,
        lease_token=body.lease_token,
        request_id=request_uuid(request),
    )
    return CustomerAssignmentReleaseResponse.model_validate(result)


@router.post(
    "/{customer_id}/assignment/takeover",
    response_model=CustomerAssignmentLeaseResponse,
)
async def takeover_customer_assignment(
    customer_id: UUID,
    body: CustomerAssignmentTakeoverRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("customer:read"))],
    service: Annotated[
        CustomerAssignmentService, Depends(get_customer_assignment_service)
    ],
) -> CustomerAssignmentLeaseResponse:
    result = await service.takeover(
        principal,
        customer_id,
        expected_version=body.expected_version,
        reason=body.reason,
        request_id=request_uuid(request),
    )
    return CustomerAssignmentLeaseResponse.model_validate(result)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("customer:read"))],
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> CustomerResponse:
    row = await service.get_customer(principal, customer_id, request_id=request_uuid(request))
    return CustomerResponse.model_validate(row)


@router.get("/{customer_id}/overview", response_model=CustomerOverviewResponse)
async def customer_overview(
    customer_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("customer:read"))],
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> CustomerOverviewResponse:
    return CustomerOverviewResponse.model_validate(await service.overview(principal, customer_id))


@router.get("/{customer_id}/accounts", response_model=list[AccountResponse])
async def customer_accounts(
    customer_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("account:read"))],
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> list[AccountResponse]:
    return [AccountResponse.model_validate(row) for row in await service.accounts(principal, customer_id)]


@router.get("/{customer_id}/transactions", response_model=PaginatedResponse[TransactionResponse])
async def customer_transactions(
    customer_id: UUID,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("transaction:read"))],
    service: Annotated[TransactionService, Depends(get_transaction_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    date_from: date | None = None,
    date_to: date | None = None,
) -> PaginatedResponse[TransactionResponse]:
    result = await service.list_transactions(
        principal,
        customer_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        request_id=request_uuid(request),
    )
    rows, total = result
    return page_response(TransactionResponse, rows, page=page, page_size=page_size, total=total)


@router.get("/{customer_id}/transaction-summary", response_model=TransactionSummaryResponse)
async def customer_transaction_summary(
    customer_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("transaction:read"))],
    service: Annotated[TransactionService, Depends(get_transaction_service)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> TransactionSummaryResponse:
    return TransactionSummaryResponse.model_validate(
        await service.summary(
            principal, customer_id, date_from=date_from, date_to=date_to
        )
    )


@router.get("/{customer_id}/documents", response_model=list[DocumentResponse])
async def customer_documents(
    customer_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:read"))],
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> list[DocumentResponse]:
    return [
        DocumentResponse.model_validate(row)
        for row in await service.documents(principal, customer_id)
    ]


@router.get("/{customer_id}/loan-applications", response_model=list[LoanResponse])
async def customer_loans(
    customer_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> list[LoanResponse]:
    return [
        LoanResponse.model_validate(row)
        for row in await service.loan_applications(principal, customer_id)
    ]
