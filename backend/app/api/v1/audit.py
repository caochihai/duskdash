"""Auditor/admin-only append-only audit query endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import SessionDep
from app.api.v1._utils import infer_total, page_response
from app.auth.dependencies import require_permissions
from app.auth.principal import CurrentPrincipal
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditEventResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=PaginatedResponse[AuditEventResponse])
async def list_audit_events(
    _principal: Annotated[CurrentPrincipal, Depends(require_permissions("audit:read"))],
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    actor_id: UUID | None = None,
    action: str | None = Query(default=None, max_length=100),
    customer_id: UUID | None = None,
    loan_application_id: UUID | None = None,
) -> PaginatedResponse[AuditEventResponse]:
    rows = await AuditRepository(session).list(
        page=page,
        page_size=page_size,
        actor_id=actor_id,
        action=action,
        customer_id=customer_id,
        loan_application_id=loan_application_id,
    )
    return page_response(
        AuditEventResponse,
        rows,
        page=page,
        page_size=page_size,
        total=infer_total(rows),
    )
