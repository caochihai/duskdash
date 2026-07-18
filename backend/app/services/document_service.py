"""Document retrieval, human verification, and authorized download use cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from app.services.access import require_permission
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike


class DocumentRepositoryLike(Protocol):
    async def get_document(self, document_id: UUID) -> Mapping[str, Any] | None: ...

    async def get_versions(self, document_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def get_version(self, document_version_id: UUID) -> Mapping[str, Any] | None: ...

    async def get_processing(self, document_version_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def get_fields(self, document_version_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def update_field(
        self,
        field_id: UUID,
        *,
        verification_status: str,
        corrected_value_text: str | None,
        verification_reason: str,
        verified_by: UUID,
    ) -> Mapping[str, Any] | None: ...


class StorageLike(Protocol):
    async def create_presigned_get(
        self,
        bucket: str,
        key: str,
        *,
        expires_in_seconds: int | None = None,
        version_id: str | None = None,
    ) -> Any: ...


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepositoryLike,
        storage: StorageLike,
        *,
        presigned_ttl_seconds: int = 600,
        audit: AuditService | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._presigned_ttl_seconds = presigned_ttl_seconds
        self._audit = audit

    async def get_document(self, principal: PrincipalLike, document_id: UUID) -> Mapping[str, Any]:
        require_permission(principal, "document:read")
        row = await self._repository.get_document(document_id)
        if row is None:
            raise LookupError("Document was not found or is outside the authorized scope")
        return row

    async def get_versions(
        self, principal: PrincipalLike, document_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "document:read")
        return await self._repository.get_versions(document_id)

    async def get_version(
        self, principal: PrincipalLike, document_version_id: UUID
    ) -> Mapping[str, Any]:
        require_permission(principal, "document:read")
        row = await self._repository.get_version(document_version_id)
        if row is None:
            raise LookupError("Document version was not found or is outside the authorized scope")
        return row

    async def get_processing(
        self, principal: PrincipalLike, document_version_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "document:read")
        return await self._repository.get_processing(document_version_id)

    async def get_fields(
        self, principal: PrincipalLike, document_version_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "document:read")
        return await self._repository.get_fields(document_version_id)

    async def verify_field(
        self,
        principal: PrincipalLike,
        field_id: UUID,
        *,
        verification_status: str,
        corrected_value_text: str | None,
        verification_reason: str,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "document:verify")
        allowed = {"VERIFIED", "CORRECTED", "REJECTED", "NEEDS_REVIEW"}
        if verification_status not in allowed:
            raise ValueError(f"verification_status must be one of {sorted(allowed)}")
        if verification_status == "CORRECTED" and not corrected_value_text:
            raise ValueError("A corrected value is required when verification_status is CORRECTED")
        if not verification_reason.strip():
            raise ValueError("A verification reason is required")
        row = await self._repository.update_field(
            field_id,
            verification_status=verification_status,
            corrected_value_text=corrected_value_text,
            verification_reason=verification_reason,
            verified_by=principal.employee_id,
        )
        if row is None:
            raise LookupError("Document field was not found or is outside the authorized scope")
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="DOCUMENT_FIELD_CORRECTED",
                resource_type="DOCUMENT_FIELD",
                resource_id=field_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={"verification_status": verification_status},
            )
        return row

    async def download_url(
        self,
        principal: PrincipalLike,
        document_version_id: UUID,
        *,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "document:download")
        row = await self.get_version(principal, document_version_id)
        bucket = str(row["bucket_name"])
        key = str(row["object_key"])
        presigned = await self._storage.create_presigned_get(
            bucket,
            key,
            expires_in_seconds=self._presigned_ttl_seconds,
            version_id=row.get("object_version_id"),
        )
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="DOCUMENT_DOWNLOADED",
                resource_type="DOCUMENT_VERSION",
                resource_id=document_version_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={"bucket": bucket},
            )
        return {"url": presigned.url, "expires_in": presigned.expires_in_seconds}

    async def page_preview_url(
        self,
        principal: PrincipalLike,
        document_version_id: UUID,
        page_number: int,
    ) -> Mapping[str, Any]:
        require_permission(principal, "document:read")
        if page_number <= 0:
            raise ValueError("page_number must be positive")
        version = await self.get_version(principal, document_version_id)
        document_id = UUID(str(version["document_id"]))
        key = f"documents/{document_id}/versions/{document_version_id}/pages/{page_number:04d}.png"
        presigned = await self._storage.create_presigned_get(
            "customer-doc-derived",
            key,
            expires_in_seconds=self._presigned_ttl_seconds,
        )
        return {"url": presigned.url, "expires_in": presigned.expires_in_seconds}
