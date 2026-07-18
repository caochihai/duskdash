"""Deterministic OCR used when no external provider is configured."""

from __future__ import annotations

from app.providers.ocr.base import OCRPage, OCRResult


class MockOCRProvider:
    provider = "mock"
    model_name = "mock-ocr"
    model_version = "1"

    def __init__(self, *, confidence: float = 0.99, fixed_text: str | None = None) -> None:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("OCR confidence must be between zero and one")
        self._confidence = confidence
        self._fixed_text = fixed_text

    async def extract(self, content: bytes, *, mime_type: str) -> OCRResult:
        if not content:
            raise ValueError("cannot OCR empty content")
        if mime_type not in {"application/pdf", "image/png", "image/jpeg", "image/tiff"}:
            raise ValueError(f"unsupported OCR MIME type: {mime_type}")
        if self._fixed_text is not None:
            text = self._fixed_text
        else:
            text = content.decode("utf-8", errors="replace")
            if not text.strip() or text.count("\ufffd") > max(3, len(text) // 4):
                text = "MOCK OCR DOCUMENT"
        page_texts = text.split("\f")
        pages = tuple(
            OCRPage(page_number=index, text=page.strip(), confidence=self._confidence)
            for index, page in enumerate(page_texts, start=1)
        )
        return OCRResult(
            pages=pages,
            provider=self.provider,
            model_name=self.model_name,
            model_version=self.model_version,
        )
