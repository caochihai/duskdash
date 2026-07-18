"""Presigned document upload orchestration with transactional Outbox creation."""

from __future__ import annotations

import base64
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.services.access import require_permission
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike
from app.services.state_machine import UPLOAD_TRANSITIONS, require_transition

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
    }
)
DOCUMENT_STEPS = (
    "VALIDATE_UPLOAD",
    "SECURITY_SCAN",
    "PERSIST_ORIGINAL",
    "OCR",
    "CLASSIFICATION",
    "FIELD_EXTRACTION",
    "NORMALIZATION",
    "FIELD_VALIDATION",
    "PAGE_GENERATION",
    "CHUNKING",
    "EMBEDDING",
    "MARK_READY",
)


class UploadRepositoryLike(Protocol):
    async def create_upload(self, values: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def get_upload(self, upload_id: UUID) -> Mapping[str, Any] | None: ...

    async def complete_upload(
        self,
        *,
        upload_id: UUID,
        object_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        job_id: UUID,
        correlation_id: UUID,
        outbox_id: UUID,
        actor_id: UUID,
        steps: tuple[str, ...],
        event: Mapping[str, Any],
        headers: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class StorageLike(Protocol):
    async def create_presigned_put(
        self,
        bucket: str,
        key: str,
        *,
        content_type: str,
        expires_in_seconds: int | None = None,
        checksum_sha256_base64: str | None = None,
    ) -> Any: ...

    async def stat_object(self, bucket: str, key: str) -> Any: ...


def validate_upload_request(
    *,
    filename: str,
    mime_type: str,
    size_bytes: int,
    sha256: str,
    max_size_bytes: int,
) -> None:
    if not filename or PurePath(filename).name != filename or len(filename) > 255:
        raise ValueError("original_filename must be a safe basename of at most 255 characters")
    if any(ord(character) < 32 for character in filename):
        raise ValueError("original_filename contains a control character")
    if mime_type not in _ALLOWED_MIME_TYPES:
        raise ValueError("Unsupported document MIME type")
    if size_bytes <= 0 or size_bytes > max_size_bytes:
        raise ValueError("Document size is outside the permitted range")
    if not _SHA256_RE.fullmatch(sha256.lower()):
        raise ValueError("expected_sha256 must contain 64 lowercase hexadecimal characters")


class UploadService:
    def __init__(
        self,
        repository: UploadRepositoryLike,
        storage: StorageLike,
        *,
        max_size_bytes: int,
        presigned_ttl_seconds: int = 600,
        audit: AuditService | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_size_bytes = max_size_bytes
        self._presigned_ttl_seconds = presigned_ttl_seconds
        self._audit = audit

    async def create_upload(
        self,
        principal: PrincipalLike,
        *,
        customer_id: UUID,
        loan_application_id: UUID | None,
        expected_document_type: str | None,
        original_filename: str,
        expected_mime_type: str,
        expected_size_bytes: int,
        expected_sha256: str,
        idempotency_key: UUID,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "document:upload")
        validate_upload_request(
            filename=original_filename,
            mime_type=expected_mime_type,
            size_bytes=expected_size_bytes,
            sha256=expected_sha256,
            max_size_bytes=self._max_size_bytes,
        )
        upload_id = uuid4()
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self._presigned_ttl_seconds)
        object_key = f"uploads/{upload_id}/incoming"
        row = await self._repository.create_upload(
            {
                "id": upload_id,
                "customer_id": customer_id,
                "loan_application_id": loan_application_id,
                "expected_document_type": expected_document_type,
                "original_filename": original_filename,
                "expected_mime_type": expected_mime_type,
                "expected_size_bytes": expected_size_bytes,
                "expected_sha256": expected_sha256.lower(),
                "quarantine_object_key": object_key,
                "status": "CREATED",
                "expires_at": expires_at,
                "created_by": principal.employee_id,
                "idempotency_key": idempotency_key,
                "created_at": now,
            }
        )
        checksum_base64 = base64.b64encode(bytes.fromhex(expected_sha256.lower())).decode("ascii")
        presigned = await self._storage.create_presigned_put(
            "upload-quarantine",
            object_key,
            content_type=expected_mime_type,
            expires_in_seconds=self._presigned_ttl_seconds,
            checksum_sha256_base64=checksum_base64,
        )
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="DOCUMENT_UPLOAD_CREATED",
                resource_type="UPLOAD_SESSION",
                resource_id=upload_id,
                customer_id=customer_id,
                loan_application_id=loan_application_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={"mime_type": expected_mime_type, "size_bytes": expected_size_bytes},
            )
        return {
            **dict(row),
            "upload_id": upload_id,
            "upload_url": presigned.url,
            "headers": dict(presigned.headers),
            "expires_at": expires_at,
        }

    async def complete_upload(
        self,
        principal: PrincipalLike,
        upload_id: UUID,
        *,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "document:upload")
        upload = await self._repository.get_upload(upload_id)
        if upload is None:
            raise LookupError("Upload session was not found or is outside the authorized scope")
        current_status = str(upload["status"])
        if current_status == "COMPLETED":
            return upload
        require_transition(current_status, "UPLOADED", UPLOAD_TRANSITIONS)
        expires_at = upload["expires_at"]
        if isinstance(expires_at, datetime) and expires_at <= datetime.now(UTC):
            raise TimeoutError("Upload session has expired")

        stat = await self._storage.stat_object("upload-quarantine", str(upload["quarantine_object_key"]))
        actual_size = int(getattr(stat, "size_bytes", 0))
        if actual_size != int(upload["expected_size_bytes"]):
            raise ValueError("Uploaded object size does not match the upload session")
        actual_checksum_base64 = getattr(stat, "checksum_sha256_base64", None)
        expected_checksum_base64 = base64.b64encode(
            bytes.fromhex(str(upload["expected_sha256"]).lower())
        ).decode("ascii")
        if actual_checksum_base64 != expected_checksum_base64:
            raise ValueError("Uploaded object checksum does not match the upload session")

        object_id = uuid4()
        document_id = uuid4()
        document_version_id = uuid4()
        job_id = uuid4()
        correlation_id = request_id or uuid4()
        outbox_id = uuid4()
        occurred_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        event = {
            "event_id": str(outbox_id),
            "event_type": "document.processing.requested",
            "event_version": 1,
            "occurred_at": occurred_at,
            "producer": "bank-api",
            "correlation_id": str(correlation_id),
            "causation_id": None,
            "partition_key": str(document_version_id),
            "actor": {"type": "EMPLOYEE", "id": str(principal.employee_id)},
            "resource": {"type": "DOCUMENT_VERSION", "id": str(document_version_id)},
            "payload": {"job_id": str(job_id), "upload_id": str(upload_id)},
            "metadata": {
                "trace_id": str(correlation_id),
                "schema": "document.processing.requested.v1",
            },
        }
        result = await self._repository.complete_upload(
            upload_id=upload_id,
            object_id=object_id,
            document_id=document_id,
            document_version_id=document_version_id,
            job_id=job_id,
            correlation_id=correlation_id,
            outbox_id=outbox_id,
            actor_id=principal.employee_id,
            steps=DOCUMENT_STEPS,
            event=event,
            headers={"topic": "bank.document.commands.v1"},
        )
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="DOCUMENT_UPLOADED",
                resource_type="DOCUMENT_VERSION",
                resource_id=document_version_id,
                customer_id=UUID(str(upload["customer_id"])),
                loan_application_id=(
                    UUID(str(upload["loan_application_id"])) if upload.get("loan_application_id") else None
                ),
                result="SUCCESS",
                request_id=request_id,
                correlation_id=correlation_id,
                metadata={"job_id": job_id},
            )
        return result
