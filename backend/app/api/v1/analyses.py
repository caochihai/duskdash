"""Analysis case state, tasks, findings, history, and retry endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.dependencies import get_analysis_service, get_loan_service
from app.api.v1._utils import request_uuid
from app.auth.dependencies import require_permissions
from app.auth.principal import CurrentPrincipal
from app.schemas.analysis import AnalysisCaseResponse
from app.schemas.evidence import FindingResponse
from app.services.analysis_service import AnalysisService
from app.services.loan_service import LoanService

router = APIRouter(prefix="/analysis-cases", tags=["analysis"])


@router.get("/{analysis_case_id}", response_model=AnalysisCaseResponse)
async def get_analysis_case(
    analysis_case_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> AnalysisCaseResponse:
    return AnalysisCaseResponse.model_validate(await service.get(principal, analysis_case_id))


@router.get("/{analysis_case_id}/tasks", response_model=list[dict[str, Any]])
async def get_analysis_tasks(
    analysis_case_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> list[dict[str, Any]]:
    return [dict(row) for row in await service.tasks(principal, analysis_case_id)]


@router.get("/{analysis_case_id}/findings", response_model=list[FindingResponse])
async def get_analysis_findings(
    analysis_case_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> list[FindingResponse]:
    return [
        FindingResponse.model_validate(row)
        for row in await service.findings(principal, analysis_case_id)
    ]


@router.get("/{analysis_case_id}/events", response_model=list[dict[str, Any]])
async def get_analysis_events(
    analysis_case_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> list[dict[str, Any]]:
    return [dict(row) for row in await service.events(principal, analysis_case_id)]


@router.post(
    "/{analysis_case_id}/retry",
    response_model=AnalysisCaseResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_analysis_case(
    analysis_case_id: UUID,
    request: Request,
    _idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:analyze"))],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
    loan_service: Annotated[LoanService, Depends(get_loan_service)],
) -> AnalysisCaseResponse:
    current = await service.get(principal, analysis_case_id)
    loan_application_id = current.get("loan_application_id")
    if loan_application_id is None:
        raise ValueError("Loan analysis is missing its loan application reference")
    await loan_service.require_assigned_handler(
        principal, UUID(str(loan_application_id))
    )
    return AnalysisCaseResponse.model_validate(
        await service.retry(
            principal,
            analysis_case_id,
            request_id=request_uuid(request),
        )
    )
