"""OCR worker — trái tim của luồng OCR bất đồng bộ (1 box, Redis queue).

Vòng đời một job:
  Platform upload → enqueue OcrJob (Redis) → [worker này] gọi OCR service →
  lưu dòng+bbox vào Postgres → set document.processing_status = OCR_READY.
Lỗi → RedisQueue tự retry (attempt+1), quá số lần → dead-letter + OCR_FAILED.

Chạy:  python -m services.worker.ocr_worker
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx  # noqa: E402

from services.common.db import get_pool  # noqa: E402
from services.common.redis_queue import RedisQueue  # noqa: E402
from services.worker.config import WorkerSettings  # noqa: E402

settings = WorkerSettings()


async def _call_ocr(job: dict) -> dict:
    body: dict = {"document_id": job["document_id"], "mime_type": job["mime_type"]}
    if job.get("file_url"):
        body["file_url"] = job["file_url"]
    elif job.get("file_b64"):
        body["file_b64"] = job["file_b64"]
    else:
        raise RuntimeError("job thiếu file_url/file_b64 để OCR")
    async with httpx.AsyncClient(timeout=settings.ocr_timeout) as client:
        resp = await client.post(f"{settings.ocr_service_url}/ocr/extract", json=body)
        resp.raise_for_status()
        return resp.json()


async def _persist(job: dict, doc: dict) -> None:
    pool = await get_pool(settings.database_url)
    version_id = job["document_version_id"]
    document_id = job["document_id"]
    provider = doc.get("provider")
    model = doc.get("model")

    async with pool.acquire() as con:
        async with con.transaction():
            # idempotent: xoá kết quả cũ của version này trước khi ghi lại
            await con.execute(
                "DELETE FROM document.document_line WHERE document_version_id = $1",
                version_id,
            )
            for page in doc["pages"]:
                page_no = int(page["page"])
                await con.execute(
                    """
                    INSERT INTO document.document_page
                        (id, document_version_id, page_number, text_content,
                         ocr_confidence, width, height, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7, now())
                    ON CONFLICT (document_version_id, page_number)
                    DO UPDATE SET text_content = EXCLUDED.text_content,
                                  width = EXCLUDED.width, height = EXCLUDED.height
                    """,
                    uuid.uuid4(), version_id, page_no,
                    "\n".join(ln["text"] for ln in page["lines"]),
                    _avg_conf(page["lines"]),
                    int(round(page["width"])), int(round(page["height"])),
                )
                for idx, line in enumerate(page["lines"]):
                    await con.execute(
                        """
                        INSERT INTO document.document_line
                            (id, document_version_id, page_number, line_index,
                             text_content, bbox, confidence, words,
                             ocr_provider, ocr_model)
                        VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8::jsonb,$9,$10)
                        """,
                        uuid.uuid4(), version_id, page_no, idx,
                        line["text"], json.dumps(_xywh(line["bbox"])),
                        line.get("confidence"),
                        json.dumps([_word(w) for w in line.get("words", [])]),
                        provider, model,
                    )
            await con.execute(
                """
                UPDATE document.document
                   SET processing_status = 'OCR_READY', updated_at = now()
                 WHERE id = $1
                """,
                document_id,
            )


async def _mark_failed(document_id: str) -> None:
    try:
        pool = await get_pool(settings.database_url)
        async with pool.acquire() as con:
            await con.execute(
                "UPDATE document.document SET processing_status='OCR_FAILED', "
                "updated_at=now() WHERE id=$1",
                document_id,
            )
    except Exception:  # noqa: BLE001 - best-effort
        pass


def _xywh(bbox: dict) -> dict:
    return {"x": bbox["x"], "y": bbox["y"], "w": bbox["w"], "h": bbox["h"]}


def _word(word: dict) -> dict:
    b = word["bbox"]
    return {"text": word["text"], "x": b["x"], "y": b["y"], "w": b["w"],
            "h": b["h"], "confidence": word.get("confidence")}


def _avg_conf(lines: list) -> float | None:
    vals = [ln["confidence"] for ln in lines if ln.get("confidence") is not None]
    return round(sum(vals) / len(vals), 5) if vals else None


async def handle(job: dict) -> None:
    doc = await _call_ocr(job)
    await _persist(job, doc)
    print(f"[ocr-worker] OCR_READY document={job['document_id']} "
          f"pages={len(doc['pages'])} provider={doc.get('provider')}")


async def main() -> None:
    if not settings.database_url:
        raise SystemExit("thiếu DATABASE_URL")
    queue = RedisQueue(
        settings.redis_url, settings.queue_name,
        max_attempts=settings.max_attempts,
    )
    print(f"[ocr-worker] listening queue='{settings.queue_name}' "
          f"ocr={settings.ocr_service_url}")

    async def _wrapped(job: dict) -> None:
        try:
            await handle(job)
        except Exception:
            # lần thử cuối → đánh dấu FAILED (RedisQueue vẫn xử lý retry/dead-letter)
            if int(job.get("attempt", 0)) + 1 >= settings.max_attempts:
                await _mark_failed(job.get("document_id", ""))
            raise

    await queue.run(_wrapped)


if __name__ == "__main__":
    asyncio.run(main())
