"""Finding and traceable evidence endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_evidence_service
from app.api.v1._utils import request_uuid
from app.auth.dependencies import require_permissions
from app.auth.principal import CurrentPrincipal
from app.schemas.evidence import EvidenceResponse, FindingResponse
from app.services.evidence_service import EvidenceService

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("/{finding_id}", response_model=FindingResponse)
async def get_finding(
    finding_id: UUID,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> FindingResponse:
    return FindingResponse.model_validate(
        await service.finding(principal, finding_id, request_id=request_uuid(request))
    )


@router.get("/{finding_id}/evidence", response_model=list[EvidenceResponse])
async def get_finding_evidence(
    finding_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("loan:read"))],
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> list[EvidenceResponse]:
    return [
        EvidenceResponse.model_validate(row)
        for row in await service.evidence(principal, finding_id)
    ]
