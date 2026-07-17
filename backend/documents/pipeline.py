"""Document ingestion and native-text extraction.

OCR is deliberately an adapter boundary: scanned documents are marked for OCR
when the optional provider is unavailable instead of being silently accepted.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path

from common import config
from common.schemas import new_id
from gateway import db
from . import extractors, ocr, validators

ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}


class DocumentValidationError(ValueError):
    pass


def detect_mime(content: bytes, filename: str) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def ingest(case_id: str, document_type: str, filename: str, content: bytes) -> dict:
    if not content:
        raise DocumentValidationError("Document is empty")
    if len(content) > config.MAX_DOCUMENT_SIZE_BYTES:
        raise DocumentValidationError("Document exceeds configured maximum size")
    mime_type = detect_mime(content, filename)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise DocumentValidationError("Only PDF, PNG, and JPEG documents are allowed")

    document_id = new_id("doc")
    file_hash = hashlib.sha256(content).hexdigest()
    suffix = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}[mime_type]
    storage_path = config.UPLOADS_DIR / f"{document_id}{suffix}"
    storage_path.write_bytes(content)
    document = {
        "document_id": document_id,
        "case_id": case_id,
        "document_type": document_type,
        "file_hash": file_hash,
        "mime_type": mime_type,
        "storage_path": str(storage_path),
        "original_filename": Path(filename).name,
        "processing_status": "queued",
        "metadata": {},
    }
    try:
        db.save_document(document)
    except Exception:
        storage_path.unlink(missing_ok=True)
        raise
    return document


def process(document_id: str) -> dict:
    document = db.get_document(document_id)
    if document is None:
        raise KeyError(f"Document not found: {document_id}")
    db.update_document(document_id, processing_status="processing")
    path = Path(document["storage_path"])
    if document["mime_type"] != "application/pdf":
        try:
            ocr_blocks = ocr.extract_image(path.read_bytes())
        except ocr.OCRUnavailable as exc:
            db.update_document(document_id, processing_status="needs_ocr", metadata={"reason": str(exc)})
            return db.get_document(document_id) or document
        blocks = [{**block, "page": 1} for block in ocr_blocks]
        facts = [_raw_fact(block, "tesseract-v1") for block in blocks]
        facts.extend(extractors.extract(document["document_type"], blocks))
        db.save_extracted_facts(document_id, facts)
        db.update_document(document_id, processing_status="completed", metadata={"page_count": 1,
                           "ocr_blocks": len(blocks), "cross_checks": validators.cross_validate(document["case_id"])})
        return db.get_document(document_id) or document

    try:
        import fitz  # PyMuPDF
    except ImportError:
        db.update_document(document_id, processing_status="needs_ocr",
                           metadata={"reason": "pymupdf_provider_not_installed"})
        return db.get_document(document_id) or document

    pdf = fitz.open(path)
    if len(pdf) > config.MAX_DOCUMENT_PAGES:
        page_count = len(pdf)
        pdf.close()
        db.update_document(document_id, processing_status="failed",
                           metadata={"reason": "page_limit_exceeded", "pages": page_count})
        return db.get_document(document_id) or document

    facts: list[dict] = []
    scanned_pages: list[int] = []
    low_confidence_pages: list[int] = []
    ocr_unavailable_pages: list[int] = []
    for page_no, page in enumerate(pdf, start=1):
        blocks = page.get_text("blocks")
        text = "\n".join(block[4].strip() for block in blocks if block[4].strip())
        if len(re.sub(r"\s+", "", text)) < 20:
            scanned_pages.append(page_no)
            try:
                # 250 DPI is a practical OCR balance between quality and latency.
                rendered = page.get_pixmap(matrix=fitz.Matrix(250 / 72, 250 / 72), alpha=False)
                ocr_blocks = [{**block, "page": page_no}
                              for block in ocr.extract_image(rendered.tobytes("png"))]
            except ocr.OCRUnavailable:
                ocr_unavailable_pages.append(page_no)
                continue
            if not ocr_blocks or sum(b["confidence"] for b in ocr_blocks) / len(ocr_blocks) < 0.60:
                low_confidence_pages.append(page_no)
            for block in ocr_blocks:
                facts.append(_raw_fact(block, "tesseract-v1"))
            continue
        for index, block in enumerate(blocks):
            excerpt = block[4].strip()
            if not excerpt:
                continue
            facts.append(_raw_fact({"text": excerpt, "page": page_no, "bbox": list(block[:4])},
                                   "pymupdf-native-text-v1"))
    page_count = len(pdf)
    pdf.close()
    raw_blocks = [{"text": f["value"], "page": f["evidence"]["page"], "bbox": f["evidence"]["bbox"]}
                  for f in facts]
    facts.extend(extractors.extract(document["document_type"], raw_blocks))
    db.save_extracted_facts(document_id, facts)
    # Pages remain in needs-review only when OCR was unavailable or confidence was low.
    status = "needs_ocr" if (low_confidence_pages or ocr_unavailable_pages) else "completed"
    db.update_document(document_id, processing_status=status, metadata={
        "page_count": page_count, "native_text_blocks": len(raw_blocks), "ocr_required_pages": scanned_pages,
        "ocr_low_confidence_pages": low_confidence_pages,
        "ocr_unavailable_pages": ocr_unavailable_pages,
        "cross_checks": validators.cross_validate(document["case_id"]),
    })
    return db.get_document(document_id) or document


def _raw_fact(block: dict, extractor_version: str) -> dict:
    excerpt = block["text"].strip()
    return {"fact_id": new_id("fact"), "key": "raw_text_block", "value": excerpt,
            "normalized_value": excerpt.lower(), "confidence": block.get("confidence", 1.0),
            "evidence": {"page": block["page"], "bbox": block.get("bbox"), "text": excerpt[:500]},
            "extractor_version": extractor_version}
