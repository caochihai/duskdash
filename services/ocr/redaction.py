"""Bôi đen (redaction) theo bbox chuẩn hoá — lý do chính đổi sang OCR truyền thống.

Ảnh: vẽ chữ nhật đen bằng Pillow. PDF: dùng PyMuPDF add_redact_annot + apply
(xoá hẳn nội dung bên dưới, không chỉ che). BBox toạ độ 0..1 → quy đổi theo trang.
"""

from __future__ import annotations

import io
from collections.abc import Sequence

from libs.contracts.geometry import BBox


def redact(content: bytes, *, mime_type: str, boxes: Sequence[BBox]) -> bytes:
    if mime_type.startswith("image/"):
        return _redact_image(content, boxes)
    if mime_type == "application/pdf":
        return _redact_pdf(content, boxes)
    raise ValueError(f"redaction chưa hỗ trợ mime type: {mime_type}")


def _redact_image(content: bytes, boxes: Sequence[BBox]) -> bytes:
    from PIL import Image, ImageDraw  # import trễ để service khởi động nhẹ

    image = Image.open(io.BytesIO(content)).convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)
    for box in boxes:
        if box.page != 1:  # ảnh chỉ có 1 trang
            continue
        x0, y0, x1, y1 = box.to_pixels(width, height)
        draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _redact_pdf(content: bytes, boxes: Sequence[BBox]) -> bytes:
    import fitz  # PyMuPDF

    doc = fitz.open(stream=content, filetype="pdf")
    try:
        by_page: dict[int, list[BBox]] = {}
        for box in boxes:
            by_page.setdefault(box.page, []).append(box)
        for page_number, page_boxes in by_page.items():
            if page_number < 1 or page_number > doc.page_count:
                continue
            page = doc[page_number - 1]
            pw, ph = page.rect.width, page.rect.height
            for box in page_boxes:
                x0, y0, x1, y1 = box.to_pixels(pw, ph)
                page.add_redact_annot(fitz.Rect(x0, y0, x1, y1), fill=(0, 0, 0))
            page.apply_redactions()
        return doc.tobytes()
    finally:
        doc.close()
