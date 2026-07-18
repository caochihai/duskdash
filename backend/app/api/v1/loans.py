"""Loan application workflow and human-only decision endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.dependencies import SessionDep, get_analysis_service, get_loan_service
from app.api.idempotency import execute_idempotent
from app.api.v1._utils import request_uuid
from app.auth.dependencies import require_permissions
from app.auth.principal import CurrentPrincipal
from app.schemas.analysis import AnalysisCaseResponse
from app.schemas.loan import (
    AnalysisRequest,
    LoanCreateRequest,
    LoanDecisionRequest,
    LoanPartyRequest,
    LoanResponse,
    LoanUpdateRequest,
    SubmitLoanRequest,
)
from app.services.analysis_service import AnalysisService
from app.services.loan_service import LoanService

router = APIRouter(prefix="/loan-applications", tags=["loan-applications"])


@router.post("", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
async def create_loan_application(
    body: LoanCreateRequest,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:create"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
    session: SessionDep,
) -> LoanResponse:
    payload = body.model_dump(mode="json", exclude_none=True)
    row = await execute_idempotent(
        session=session,
        actor_id=principal.employee_id,
        operation_name="CREATE_LOAN_APPLICATION",
        idempotency_key=idempotency_key,
        request_payload=payload,
        response_status=status.HTTP_201_CREATED,
        resource_type="LOAN_APPLICATION",
        operation=lambda: service.create(principal, body.model_dump(exclude_none=True)),
    )
    return LoanResponse.model_validate(row)


@router.get("/{loan_application_id}", response_model=LoanResponse)
async def get_loan_application(
    loan_application_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
) -> LoanResponse:
    return LoanResponse.model_validate(await service.get(principal, loan_application_id))


@router.patch("/{loan_application_id}", response_model=LoanResponse)
async def update_loan_application(
    loan_application_id: UUID,
    body: LoanUpdateRequest,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:update"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
) -> LoanResponse:
    values = body.model_dump(exclude_none=True)
    expected_version = int(values.pop("version"))
    return LoanResponse.model_validate(
        await service.update(
            principal,
            loan_application_id,
            values,
            expected_version=expected_version,
        )
    )


@router.post("/{loan_application_id}/parties", response_model=dict[str, Any])
async def add_loan_party(
    loan_application_id: UUID,
    body: LoanPartyRequest,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:update"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
) -> dict[str, Any]:
    return dict(
        await service.add_party(
            principal,
            loan_application_id,
            party_id=body.party_id,
            party_role=body.party_role,
        )
    )


@router.post("/{loan_application_id}/documents/{document_id}", response_model=dict[str, Any])
async def link_loan_document(
    loan_application_id: UUID,
    document_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:update"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
) -> dict[str, Any]:
    return dict(await service.link_document(principal, loan_application_id, document_id))


@router.get("/{loan_application_id}/checklist", response_model=list[dict[str, Any]])
async def get_loan_checklist(
    loan_application_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
) -> list[dict[str, Any]]:
    return [dict(row) for row in await service.checklist(principal, loan_application_id)]


@router.get("/{loan_application_id}/calculations", response_model=list[dict[str, Any]])
async def get_loan_calculations(
    loan_application_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
) -> list[dict[str, Any]]:
    return [dict(row) for row in await service.calculations(principal, loan_application_id)]


@router.get("/{loan_application_id}/policy-checks", response_model=list[dict[str, Any]])
async def get_loan_policy_checks(
    loan_application_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
) -> list[dict[str, Any]]:
    return [dict(row) for row in await service.policy_checks(principal, loan_application_id)]


@router.post(
    "/{loan_application_id}/analyses",
    response_model=AnalysisCaseResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_loan_analysis(
    loan_application_id: UUID,
    body: AnalysisRequest,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:analyze"))],
    loan_service: Annotated[LoanService, Depends(get_loan_service)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    session: SessionDep,
) -> AnalysisCaseResponse:
    # Analysis is a processing action, so only the employee currently assigned
    # to this application (or an authorized manager) may start it. Read-only
    # access remains available through the normal GET endpoints.
    loan = await loan_service.require_assigned_handler(principal, loan_application_id)
    payload = {"loan_application_id": str(loan_application_id), **body.model_dump(mode="json")}
    row = await execute_idempotent(
        session=session,
        actor_id=principal.employee_id,
        operation_name="REQUEST_LOAN_ANALYSIS",
        idempotency_key=idempotency_key,
        request_payload=payload,
        response_status=status.HTTP_202_ACCEPTED,
        resource_type="ANALYSIS_CASE",
        operation=lambda: analysis_service.request(
            principal,
            customer_id=UUID(str(loan["primary_customer_id"])),
            loan_application_id=loan_application_id,
            objective=body.objective,
            request_id=request_uuid(request),
        ),
    )
    return AnalysisCaseResponse.model_validate(row)


@router.get("/{loan_application_id}/analyses", response_model=list[AnalysisCaseResponse])
async def list_loan_analyses(
    loan_application_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
) -> list[AnalysisCaseResponse]:
    return [
        AnalysisCaseResponse.model_validate(row)
        for row in await service.analyses(principal, loan_application_id)
    ]


@router.post("/{loan_application_id}/submit", response_model=LoanResponse)
async def submit_loan_application(
    loan_application_id: UUID,
    body: SubmitLoanRequest,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:submit"))],
    service: Annotated[LoanService, Depends(get_loan_service)],
    session: SessionDep,
) -> LoanResponse:
    row = await execute_idempotent(
        session=session,
        actor_id=principal.employee_id,
        operation_name="SUBMIT_LOAN_APPLICATION",
        idempotency_key=idempotency_key,
        request_payload={"loan_application_id": str(loan_application_id), **body.model_dump()},
        response_status=status.HTTP_200_OK,
        resource_type="LOAN_APPLICATION",
        operation=lambda: service.submit(
            principal,
            loan_application_id,
            expected_version=body.version,
            request_id=request_uuid(request),
        ),
    )
    return LoanResponse.model_validate(row)


@router.post("/{loan_application_id}/decisions", response_model=dict[str, Any])
async def create_loan_decision(
    loan_application_id: UUID,
    body: LoanDecisionRequest,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permissions("loan:approve")),
    ],
    service: Annotated[LoanService, Depends(get_loan_service)],
    session: SessionDep,
) -> dict[str, Any]:
    payload = {"loan_application_id": str(loan_application_id), **body.model_dump(mode="json")}
    row = await execute_idempotent(
        session=session,
        actor_id=principal.employee_id,
        operation_name="CREATE_LOAN_DECISION",
        idempotency_key=idempotency_key,
        request_payload=payload,
        response_status=status.HTTP_200_OK,
        resource_type="LOAN_DECISION",
        operation=lambda: service.decide(
            principal,
            loan_application_id,
            decision_type=body.decision_type,
            approved_amount=body.approved_amount,
            approved_term_months=body.approved_term_months,
            conditions=body.conditions,
            rationale=body.rationale,
            approval_request_id=body.approval_request_id,
            is_override=body.is_override,
            override_reason=body.override_reason,
            request_id=request_uuid(request),
        ),
    )
    return dict(row)
