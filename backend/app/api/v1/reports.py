"""Report generation, validation claims, download, and human review endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.dependencies import SessionDep, get_report_service
from app.api.idempotency import execute_idempotent
from app.api.v1._utils import request_uuid
from app.auth.dependencies import require_permissions
from app.auth.principal import CurrentPrincipal
from app.schemas.document import PresignedURLResponse
from app.schemas.report import ReportClaimResponse, ReportRequest, ReportResponse, ReportReviewRequest
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


@router.post(
    "/analysis-cases/{analysis_case_id}/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_report(
    analysis_case_id: UUID,
    body: ReportRequest,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("report:generate"))],
    service: Annotated[ReportService, Depends(get_report_service)],
    session: SessionDep,
) -> ReportResponse:
    payload = {"analysis_case_id": str(analysis_case_id), **body.model_dump(mode="json")}
    row = await execute_idempotent(
        session=session,
        actor_id=principal.employee_id,
        operation_name="GENERATE_ANALYSIS_REPORT",
        idempotency_key=idempotency_key,
        request_payload=payload,
        response_status=status.HTTP_202_ACCEPTED,
        resource_type="REPORT",
        operation=lambda: service.request(
            principal,
            analysis_case_id,
            report_type=body.report_type,
            request_id=request_uuid(request),
        ),
    )
    return ReportResponse.model_validate(row)


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("report:read"))],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    return ReportResponse.model_validate(await service.get(principal, report_id))


@router.get("/reports/{report_id}/claims", response_model=list[ReportClaimResponse])
async def get_report_claims(
    report_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("report:read"))],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> list[ReportClaimResponse]:
    return [
        ReportClaimResponse.model_validate(row)
        for row in await service.claims(principal, report_id)
    ]


@router.get("/reports/{report_id}/download-url", response_model=PresignedURLResponse)
async def get_report_download_url(
    report_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("report:export"))],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> PresignedURLResponse:
    return PresignedURLResponse.model_validate(await service.download_url(principal, report_id))


@router.patch("/reports/{report_id}/review", response_model=ReportResponse)
async def review_report(
    report_id: UUID,
    body: ReportReviewRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("report:review"))],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    return ReportResponse.model_validate(
        await service.review(
            principal,
            report_id,
            status=body.status,
            review_note=body.review_note,
            request_id=request_uuid(request),
        )
    )
