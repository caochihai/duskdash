"""Vòng đời tài liệu & nguyên tắc gating cho OCR bất đồng bộ.

Nguyên tắc (đã chốt): OCR chạy NỀN ngay khi upload.
- Tác vụ CẦN tài liệu  → chờ trạng thái OCR_READY mới chạy.
- Tác vụ KHÔNG cần tài liệu → chạy ngay, không bị OCR chặn.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from libs.contracts._enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"        # đã lưu file gốc, chưa OCR
    OCR_PENDING = "OCR_PENDING"  # job OCR đã đưa vào hàng đợi / đang chạy
    OCR_READY = "OCR_READY"      # OCR xong, đã lưu text + bbox → dùng được
    OCR_FAILED = "OCR_FAILED"    # OCR lỗi sau số lần thử tối đa


DOCUMENT_READY_STATES: frozenset[DocumentStatus] = frozenset({DocumentStatus.OCR_READY})


def documents_ready(statuses: list[DocumentStatus]) -> bool:
    """True nếu mọi tài liệu tham chiếu đã OCR xong (gate cho tác vụ cần tài liệu)."""
    return all(s in DOCUMENT_READY_STATES for s in statuses)


class OcrJob(BaseModel):
    """Bản tin job đẩy vào Redis queue; worker tiêu thụ để gọi OCR service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: UUID
    document_version_id: UUID
    correlation_id: UUID
    object_bucket: str
    object_key: str
    mime_type: str
    file_url: str | None = None   # presigned URL (worker gọi OCR khỏi cần tự tải file)
    attempt: int = Field(default=0, ge=0)
