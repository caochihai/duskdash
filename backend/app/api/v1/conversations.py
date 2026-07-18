"""Employee-owned conversation endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi import status as http_status

from app.api.dependencies import PrincipalDep, get_conversation_service
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationMessageRequest,
    ConversationResponse,
    ConversationTurnResponse,
    ConversationUpdateRequest,
    MessageResponse,
)
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=http_status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreateRequest,
    principal: PrincipalDep,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    return ConversationResponse.model_validate(
        await service.create(
            principal,
            active_customer_id=body.active_customer_id,
            active_loan_application_id=body.active_loan_application_id,
            title=body.title,
        )
    )


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    principal: PrincipalDep,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    customer_id: UUID | None = None,
    loan_application_id: UUID | None = None,
    conversation_status: Annotated[
        str | None,
        Query(alias="status", min_length=1, max_length=20),
    ] = None,
) -> list[ConversationResponse]:
    return [
        ConversationResponse.model_validate(row)
        for row in await service.list(
            principal,
            customer_id=customer_id,
            loan_application_id=loan_application_id,
            status=conversation_status,
        )
    ]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    principal: PrincipalDep,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    return ConversationResponse.model_validate(await service.get(principal, conversation_id))


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdateRequest,
    principal: PrincipalDep,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    row = None
    if body.active_customer_id is not None:
        row = await service.set_active_customer(
            principal, conversation_id, customer_id=body.active_customer_id
        )
    if body.title is not None:
        row = await service.update_title(principal, conversation_id, title=body.title)
    return ConversationResponse.model_validate(row)


@router.post("/{conversation_id}/close", response_model=ConversationResponse)
async def close_conversation(
    conversation_id: UUID,
    principal: PrincipalDep,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    return ConversationResponse.model_validate(await service.close(principal, conversation_id))


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_conversation_messages(
    conversation_id: UUID,
    principal: PrincipalDep,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> list[MessageResponse]:
    return [
        MessageResponse.model_validate(row)
        for row in await service.messages(principal, conversation_id)
    ]


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationTurnResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def add_conversation_message(
    conversation_id: UUID,
    body: ConversationMessageRequest,
    principal: PrincipalDep,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    assignment_lease_token: Annotated[
        str | None,
        Header(
            alias="X-Customer-Assignment-Lease-Token",
            min_length=32,
            max_length=256,
        ),
    ] = None,
) -> ConversationTurnResponse:
    return ConversationTurnResponse.model_validate(
        await service.add_message(
            principal,
            conversation_id,
            content=body.content,
            attachment_ids=body.attachment_ids,
            assignment_lease_token=assignment_lease_token,
        )
    )
