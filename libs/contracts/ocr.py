"""Schema OCR dùng chung — kết quả OCR mang toạ độ (bbox) để highlight & bôi đen.

Đây là hợp đồng giữa OCR service (Máy 3) và phần còn lại. Mọi text đều kèm bbox
chuẩn hoá nên một câu trích bất kỳ đều truy được về vùng trên trang tài liệu.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from libs.contracts.geometry import BBox


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OcrWord(_Frozen):
    text: str
    bbox: BBox
    confidence: float = Field(ge=0.0, le=1.0)


class OcrLine(_Frozen):
    text: str
    bbox: BBox
    confidence: float = Field(ge=0.0, le=1.0)
    words: tuple[OcrWord, ...] = ()


class OcrPage(_Frozen):
    page: int = Field(ge=1)
    width: float = Field(gt=0)         # kích thước trang theo `unit`
    height: float = Field(gt=0)
    unit: str = "pixel"                # "pixel" (ảnh) hoặc "inch" (PDF) — theo Azure
    lines: tuple[OcrLine, ...] = ()


class OcrField(_Frozen):
    """Field có cấu trúc (tuỳ chọn) — giữ nguyên bbox để highlight ô dữ liệu."""

    name: str
    value: str
    bbox: BBox | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DocumentOCR(_Frozen):
    document_id: UUID
    provider: str                      # "azure-read" | "mock"
    model: str
    full_text: str
    pages: tuple[OcrPage, ...]
    fields: tuple[OcrField, ...] = ()


# ---- DTO cho API của OCR service ----

class OcrExtractRequest(_Frozen):
    document_id: UUID
    mime_type: str
    file_b64: str | None = None        # ưu tiên; hoặc dùng file_url
    file_url: str | None = None


class RedactionRequest(_Frozen):
    document_id: UUID
    mime_type: str
    file_b64: str
    boxes: tuple[BBox, ...]             # vùng cần bôi đen (PII)


class RedactionResult(_Frozen):
    document_id: UUID
    redacted_b64: str | None = None
    redacted_url: str | None = None
