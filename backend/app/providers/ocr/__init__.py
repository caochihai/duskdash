"""OCR provider contract."""

from app.providers.ocr.base import OCRPage, OCRProvider, OCRResult
from app.providers.ocr.mock import MockOCRProvider

__all__ = ["MockOCRProvider", "OCRPage", "OCRProvider", "OCRResult"]
