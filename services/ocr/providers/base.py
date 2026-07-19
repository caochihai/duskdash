"""Giao diện OCR provider — mọi provider trả về DocumentOCR (text + bbox)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from libs.contracts.ocr import DocumentOCR


class OcrProvider(Protocol):
    provider: str
    model: str

    async def extract(
        self, content: bytes, *, mime_type: str, document_id: UUID
    ) -> DocumentOCR: ...
