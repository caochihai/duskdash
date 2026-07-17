"""Optional Tesseract OCR provider with a deterministic unavailable outcome."""
from __future__ import annotations

import shutil


class OCRUnavailable(RuntimeError):
    pass


def extract_image(image_bytes: bytes) -> list[dict]:
    if shutil.which("tesseract") is None:
        raise OCRUnavailable("Tesseract executable is not installed")
    try:
        from PIL import Image, ImageFilter, ImageOps
        import io
        import pytesseract
    except ImportError as exc:
        raise OCRUnavailable("Install Pillow and pytesseract to enable OCR") from exc
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    # Lightweight preprocessing that is safe for both receipts and document scans.
    image = ImageOps.autocontrast(image).filter(ImageFilter.MedianFilter(size=3))
    try:
        data = pytesseract.image_to_data(
            image, lang="vie+eng", config="--oem 1 --psm 6", output_type=pytesseract.Output.DICT,
        )
    except pytesseract.TesseractError as exc:
        raise OCRUnavailable(f"Tesseract OCR failed: {exc}") from exc
    blocks = []
    for i, text in enumerate(data["text"]):
        if not text.strip():
            continue
        confidence = float(data["conf"][i]) / 100 if data["conf"][i] != "-1" else 0.0
        blocks.append({"text": text, "confidence": confidence,
                       "bbox": [data["left"][i], data["top"][i], data["width"][i], data["height"][i]]})
    return blocks
