"""Structured input/output models for document processing."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PipelineStep(StrEnum):
    VALIDATE_UPLOAD = "VALIDATE_UPLOAD"
    SECURITY_SCAN = "SECURITY_SCAN"
    PERSIST_ORIGINAL = "PERSIST_ORIGINAL"
    OCR = "OCR"
    CLASSIFICATION = "CLASSIFICATION"
    FIELD_EXTRACTION = "FIELD_EXTRACTION"
    NORMALIZATION = "NORMALIZATION"
    FIELD_VALIDATION = "FIELD_VALIDATION"
    PAGE_GENERATION = "PAGE_GENERATION"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    MARK_READY = "MARK_READY"


class DocumentPipelineInput(_FrozenModel):
    job_id: UUID
    correlation_id: UUID
    document_id: UUID
    document_version_id: UUID
    source_bucket: str = "upload-quarantine"
    source_key: str
    mime_type: str
    expected_size_bytes: int = Field(gt=0)
    expected_sha256: str

    @field_validator("expected_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("expected_sha256 must be a 64-character hexadecimal digest")
        return normalized


class PageResult(_FrozenModel):
    page_number: int = Field(ge=1)
    text_content: str
    ocr_confidence: Decimal = Field(ge=0, le=1)
    width: int | None = None
    height: int | None = None


class ExtractedFieldResult(_FrozenModel):
    field_name: str
    value_type: str
    ocr_value_text: str | None = None
    normalized_value_text: str | None = None
    value_number: Decimal | None = None
    page_number: int | None = None
    confidence: Decimal = Field(ge=0, le=1)
    verification_status: str = "UNVERIFIED"
    source_text: str | None = None


class ChunkResult(_FrozenModel):
    chunk_index: int = Field(ge=0)
    page_from: int | None = None
    page_to: int | None = None
    text_content: str
    token_count: int = Field(ge=1)
    embedding: tuple[float, ...] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IssueResult(_FrozenModel):
    issue_type: str
    severity: str
    title: str
    description: str
    status: str = "OPEN"
    detected_by: str = "SYSTEM"


class DocumentPipelineResult(_FrozenModel):
    document_id: UUID
    document_version_id: UUID
    original_bucket: str
    original_key: str
    ocr_bucket: str
    ocr_key: str
    classification: str
    classification_confidence: Decimal = Field(ge=0, le=1)
    processing_status: str
    pages: tuple[PageResult, ...]
    fields: tuple[ExtractedFieldResult, ...]
    chunks: tuple[ChunkResult, ...]
    issues: tuple[IssueResult, ...]
    provider_versions: dict[str, str]
