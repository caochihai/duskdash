"""Document upload, processing, and verification contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import APIModel, DecimalString


class UploadCreateRequest(APIModel):
    # Không truyền customer_id -> backend tự tạo khách hàng nháp từ hồ sơ
    # (tên sẽ được vision-LLM cập nhật sau khi trích xuất).
    customer_id: UUID | None = None
    loan_application_id: UUID | None = None
    expected_document_type: str | None = Field(default=None, max_length=50)
    original_filename: str = Field(min_length=1, max_length=255)
    expected_mime_type: str = Field(min_length=3, max_length=100)
    expected_size_bytes: int = Field(gt=0)
    expected_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class UploadResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    upload_id: UUID
    customer_id: UUID
    status: str
    upload_url: str
    headers: dict[str, str]
    expires_at: datetime


class UploadCompleteResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    upload_id: UUID
    document_id: UUID
    document_version_id: UUID
    job_id: UUID
    status: str


class DocumentResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    document_type: str
    classification: str
    verification_status: str
    processing_status: str
    current_version_id: UUID | None = None


class DocumentVersionResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    document_id: UUID
    version_number: int
    original_filename: str
    mime_type: str
    file_size: int
    sha256: str
    scan_status: str
    is_current: bool


class DocumentFieldResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    document_version_id: UUID
    field_name: str
    value_type: str
    ocr_value_text: str | None = None
    normalized_value_text: str | None = None
    corrected_value_text: str | None = None
    value_number: DecimalString | None = None
    confidence: DecimalString | None = None
    verification_status: str


class FieldVerificationRequest(APIModel):
    verification_status: str
    corrected_value_text: str | None = Field(default=None, max_length=4000)
    verification_reason: str = Field(min_length=1, max_length=1000)

    @field_validator("verification_status")
    @classmethod
    def status_is_supported(cls, value: str) -> str:
        allowed = {"VERIFIED", "CORRECTED", "REJECTED", "NEEDS_REVIEW"}
        if value not in allowed:
            raise ValueError(f"verification_status must be one of {sorted(allowed)}")
        return value


class PresignedURLResponse(APIModel):
    url: str
    expires_in: int

