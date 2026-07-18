"""Presigned upload and document lifecycle endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.dependencies import SessionDep, get_document_service, get_upload_service
from app.api.idempotency import execute_idempotent
from app.api.v1._utils import request_uuid
from app.auth.dependencies import require_permissions
from app.auth.principal import CurrentPrincipal
from app.schemas.document import (
    DocumentFieldResponse,
    DocumentResponse,
    DocumentVersionResponse,
    FieldVerificationRequest,
    PresignedURLResponse,
    UploadCompleteResponse,
    UploadCreateRequest,
    UploadResponse,
)
from app.services.document_service import DocumentService
from app.services.upload_service import UploadService

router = APIRouter()
documents_router = APIRouter(prefix="/documents", tags=["documents"])
versions_router = APIRouter(prefix="/document-versions", tags=["document-versions"])
fields_router = APIRouter(prefix="/document-fields", tags=["document-fields"])


@documents_router.post("/uploads", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def create_upload(
    body: UploadCreateRequest,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:upload"))],
    service: Annotated[UploadService, Depends(get_upload_service)],
    session: SessionDep,
) -> UploadResponse:
    payload = body.model_dump(mode="json", exclude_none=True)
    row = await execute_idempotent(
        session=session,
        actor_id=principal.employee_id,
        operation_name="CREATE_DOCUMENT_UPLOAD",
        idempotency_key=idempotency_key,
        request_payload=payload,
        response_status=status.HTTP_201_CREATED,
        resource_type="UPLOAD_SESSION",
        operation=lambda: service.create_upload(
            principal,
            customer_id=body.customer_id,
            loan_application_id=body.loan_application_id,
            expected_document_type=body.expected_document_type,
            original_filename=body.original_filename,
            expected_mime_type=body.expected_mime_type,
            expected_size_bytes=body.expected_size_bytes,
            expected_sha256=body.expected_sha256,
            idempotency_key=idempotency_key,
            request_id=request_uuid(request),
        ),
    )
    return UploadResponse.model_validate(row)


@documents_router.post(
    "/uploads/{upload_id}/complete",
    response_model=UploadCompleteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_upload(
    upload_id: UUID,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:upload"))],
    service: Annotated[UploadService, Depends(get_upload_service)],
    session: SessionDep,
) -> UploadCompleteResponse:
    row = await execute_idempotent(
        session=session,
        actor_id=principal.employee_id,
        operation_name="COMPLETE_DOCUMENT_UPLOAD",
        idempotency_key=idempotency_key,
        request_payload={"upload_id": str(upload_id)},
        response_status=status.HTTP_202_ACCEPTED,
        resource_type="DOCUMENT",
        operation=lambda: service.complete_upload(
            principal,
            upload_id,
            request_id=request_uuid(request),
        ),
    )
    return UploadCompleteResponse.model_validate(row)


@documents_router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    return DocumentResponse.model_validate(await service.get_document(principal, document_id))


@documents_router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def get_document_versions(
    document_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[DocumentVersionResponse]:
    return [
        DocumentVersionResponse.model_validate(row)
        for row in await service.get_versions(principal, document_id)
    ]


@versions_router.get("/{document_version_id}", response_model=DocumentVersionResponse)
async def get_document_version(
    document_version_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentVersionResponse:
    return DocumentVersionResponse.model_validate(
        await service.get_version(principal, document_version_id)
    )


@versions_router.get("/{document_version_id}/processing", response_model=list[dict[str, Any]])
async def get_document_processing(
    document_version_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[dict[str, Any]]:
    return [dict(row) for row in await service.get_processing(principal, document_version_id)]


@versions_router.get("/{document_version_id}/fields", response_model=list[DocumentFieldResponse])
async def get_document_fields(
    document_version_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[DocumentFieldResponse]:
    return [
        DocumentFieldResponse.model_validate(row)
        for row in await service.get_fields(principal, document_version_id)
    ]


@versions_router.get("/{document_version_id}/download-url", response_model=PresignedURLResponse)
async def document_download_url(
    document_version_id: UUID,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:download"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> PresignedURLResponse:
    return PresignedURLResponse.model_validate(
        await service.download_url(
            principal, document_version_id, request_id=request_uuid(request)
        )
    )


@versions_router.get(
    "/{document_version_id}/pages/{page_number}/preview-url",
    response_model=PresignedURLResponse,
)
async def document_page_preview_url(
    document_version_id: UUID,
    page_number: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> PresignedURLResponse:
    return PresignedURLResponse.model_validate(
        await service.page_preview_url(principal, document_version_id, page_number)
    )


@fields_router.patch("/{field_id}/verification", response_model=DocumentFieldResponse)
async def verify_document_field(
    field_id: UUID,
    body: FieldVerificationRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("document:verify"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentFieldResponse:
    return DocumentFieldResponse.model_validate(
        await service.verify_field(
            principal,
            field_id,
            verification_status=body.verification_status,
            corrected_value_text=body.corrected_value_text,
            verification_reason=body.verification_reason,
            request_id=request_uuid(request),
        )
    )


router.include_router(documents_router)
router.include_router(versions_router)
router.include_router(fields_router)
