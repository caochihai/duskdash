"""Storage abstractions and immutable infrastructure object-key contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from app.compat import StrEnum
from typing import Protocol
from uuid import UUID


class Bucket(StrEnum):
    """Buckets provisioned by the infrastructure project."""

    UPLOAD_QUARANTINE = "upload-quarantine"
    CUSTOMER_DOC_ORIGINAL = "customer-doc-original"
    CUSTOMER_DOC_DERIVED = "customer-doc-derived"
    POLICY_DOCUMENTS = "policy-documents"
    GENERATED_REPORTS = "generated-reports"
    AUDIT_ARCHIVE = "audit-archive"


class StorageDeleteNotPermittedError(PermissionError):
    """Raised before a runtime identity attempts an ungranted delete."""


@dataclass(frozen=True, slots=True)
class PresignedRequest:
    """A browser-safe presigned URL and the headers that must accompany it."""

    url: str
    expires_in_seconds: int
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ObjectStat:
    """Storage metadata returned by a HEAD request."""

    bucket: str
    key: str
    size_bytes: int
    etag: str | None
    content_type: str | None
    version_id: str | None
    checksum_sha256_base64: str | None
    metadata: Mapping[str, str]


class ObjectKey:
    """Generate only the UUID-based keys defined by the infra contract."""

    @staticmethod
    def upload(upload_id: UUID) -> str:
        return f"uploads/{upload_id}/incoming"

    @staticmethod
    def original(document_id: UUID, document_version_id: UUID) -> str:
        return f"documents/{document_id}/versions/{document_version_id}/original"

    @staticmethod
    def ocr_result(document_id: UUID, document_version_id: UUID) -> str:
        return f"documents/{document_id}/versions/{document_version_id}/ocr/result.json"

    @staticmethod
    def page_image(document_id: UUID, document_version_id: UUID, page_number: int) -> str:
        if page_number < 1 or page_number > 9999:
            raise ValueError("page_number must be between 1 and 9999")
        return f"documents/{document_id}/versions/{document_version_id}/pages/{page_number:04d}.png"

    @staticmethod
    def redacted_preview(document_id: UUID, document_version_id: UUID) -> str:
        return f"documents/{document_id}/versions/{document_version_id}/redacted/preview.pdf"

    @staticmethod
    def policy_original(policy_id: UUID, policy_version_id: UUID) -> str:
        return f"policies/{policy_id}/versions/{policy_version_id}/original.pdf"

    @staticmethod
    def policy_parsed(policy_id: UUID, policy_version_id: UUID) -> str:
        return f"policies/{policy_id}/versions/{policy_version_id}/parsed.json"

    @staticmethod
    def report(analysis_case_id: UUID, report_id: UUID, version: int, extension: str) -> str:
        if version < 1:
            raise ValueError("report version must be positive")
        if extension not in {"json", "pdf"}:
            raise ValueError("report extension must be json or pdf")
        return f"analysis-cases/{analysis_case_id}/reports/{report_id}/v{version}/report.{extension}"

    @staticmethod
    def audit_batch(year: int, month: int, day: int, batch_id: UUID) -> str:
        if not 1 <= month <= 12 or not 1 <= day <= 31:
            raise ValueError("invalid audit date")
        return f"audit/{year:04d}/{month:02d}/{day:02d}/events-{batch_id}.jsonl"


class Storage(Protocol):
    """Async port around S3 operations used by backend services and workers."""

    async def create_presigned_put(
        self,
        bucket: str,
        key: str,
        *,
        content_type: str,
        expires_in_seconds: int | None = None,
        checksum_sha256_base64: str | None = None,
    ) -> PresignedRequest: ...

    async def create_presigned_get(
        self,
        bucket: str,
        key: str,
        *,
        expires_in_seconds: int | None = None,
        version_id: str | None = None,
    ) -> PresignedRequest: ...

    async def stat_object(self, bucket: str, key: str, *, version_id: str | None = None) -> ObjectStat: ...

    async def object_exists(self, bucket: str, key: str, *, version_id: str | None = None) -> bool: ...

    async def get_object(self, bucket: str, key: str, *, version_id: str | None = None) -> bytes: ...

    async def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectStat: ...

    async def copy_object(
        self, source_bucket: str, source_key: str, target_bucket: str, target_key: str
    ) -> ObjectStat: ...

    async def put_object_tags(self, bucket: str, key: str, tags: Mapping[str, str]) -> None: ...

    async def remove_object(self, bucket: str, key: str, *, version_id: str | None = None) -> None: ...

    async def close(self) -> None: ...
