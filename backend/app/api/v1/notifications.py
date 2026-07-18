"""Durable employee notification endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import PrincipalDep, get_notification_service
from app.api.v1._utils import page_response
from app.schemas.common import PaginatedResponse
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    principal: PrincipalDep,
    service: Annotated[NotificationService, Depends(get_notification_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status: str | None = None,
) -> PaginatedResponse[NotificationResponse]:
    rows, total = await service.list(
        principal,
        page=page,
        page_size=page_size,
        status=status,
    )
    return page_response(
        NotificationResponse,
        rows,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    principal: PrincipalDep,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationResponse:
    return NotificationResponse.model_validate(
        await service.mark_read(principal, notification_id)
    )
