"""OCR stage wrapper."""

from __future__ import annotations

from app.providers.ocr.base import OCRProvider, OCRResult


class OCRProcessor:
    def __init__(self, provider: OCRProvider) -> None:
        self._provider = provider

    async def process(self, content: bytes, *, mime_type: str) -> OCRResult:
        return await self._provider.extract(content, mime_type=mime_type)
