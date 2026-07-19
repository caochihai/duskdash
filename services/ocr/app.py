"""OCR service (Máy 3) — FastAPI.

Endpoint:
  GET  /health
  POST /ocr/extract  -> DocumentOCR (text + bbox)
  POST /ocr/redact   -> RedactionResult (bôi đen theo bbox)

Model chạy qua API Azure remote (OCR_PROVIDER=azure) hoặc mock (mặc định).
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

# cho phép chạy trực tiếp (dev) lẫn trong container (PYTHONPATH=/app)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402

from libs.contracts.ocr import (  # noqa: E402
    DocumentOCR,
    OcrExtractRequest,
    RedactionRequest,
    RedactionResult,
)
from services.ocr import redaction  # noqa: E402
from services.ocr.config import OcrSettings  # noqa: E402
from services.ocr.providers.azure_read import AzureReadProvider  # noqa: E402
from services.ocr.providers.base import OcrProvider  # noqa: E402
from services.ocr.providers.mock import MockOcrProvider  # noqa: E402

settings = OcrSettings()
app = FastAPI(title="OCR Service", version="1.0")


def _provider() -> OcrProvider:
    if settings.provider == "azure":
        settings.validate_for_azure()
        return AzureReadProvider(
            endpoint=settings.azure_endpoint,
            key=settings.azure_key,
            model=settings.azure_model,
            api_version=settings.azure_api_version,
            poll_interval=settings.poll_interval,
            poll_timeout=settings.poll_timeout,
            http_timeout=settings.http_timeout,
        )
    return MockOcrProvider()


async def _load_bytes(req: OcrExtractRequest) -> bytes:
    if req.file_b64:
        try:
            return base64.b64decode(req.file_b64)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"file_b64 không hợp lệ: {exc}")
    if req.file_url:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.get(req.file_url)
            resp.raise_for_status()
            return resp.content
    raise HTTPException(status_code=400, detail="cần file_b64 hoặc file_url")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ocr", "provider": settings.provider}


@app.post("/ocr/extract", response_model=DocumentOCR)
async def extract(req: OcrExtractRequest) -> DocumentOCR:
    content = await _load_bytes(req)
    if not content:
        raise HTTPException(status_code=400, detail="nội dung rỗng")
    try:
        return await _provider().extract(
            content, mime_type=req.mime_type, document_id=req.document_id
        )
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=f"OCR lỗi: {exc}")


@app.post("/ocr/redact", response_model=RedactionResult)
async def redact(req: RedactionRequest) -> RedactionResult:
    try:
        content = base64.b64decode(req.file_b64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"file_b64 không hợp lệ: {exc}")
    try:
        out = redaction.redact(content, mime_type=req.mime_type, boxes=req.boxes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedactionResult(
        document_id=req.document_id,
        redacted_b64=base64.b64encode(out).decode("ascii"),
    )
