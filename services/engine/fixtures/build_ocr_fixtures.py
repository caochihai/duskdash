"""Chạy Azure OCR THẬT trên các bộ hồ sơ khách → lưu fixture bbox (resumable).

    # nạp .env rồi chạy:
    PYTHONUTF8=1 PYTHONPATH=. python -m services.engine.fixtures.build_ocr_fixtures

- Duyệt mỗi thư mục trong "Hồ sơ Doanh nghiệp, Khách hàng" (trừ gói mock).
- Mỗi ảnh: gọi Azure prebuilt-read (đồng thời tối đa CONCURRENCY, xoay 2 resource).
- Tự phát hiện case_id (regex CR-[A-Z]\\d+) từ full_text → map thư mục ↔ case.
- Lưu 1 fixture JSON / thư mục ở services/engine/fixtures/ocr/<slug>.json (gitignored).
- Resumable: ảnh đã có trong fixture thì bỏ qua (không gọi lại Azure, không tốn tiền).

document_id ổn định = uuid5(folder/filename) để Document agent tham chiếu lại được.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import uuid
from pathlib import Path

from services.ocr.providers.azure_read import AzureReadProvider

REPO = Path(__file__).resolve().parents[3]
DOCS_ROOT = REPO / "Hồ sơ Doanh nghiệp, Khách hàng"
OUT_DIR = Path(__file__).resolve().parent / "ocr"
_NS = uuid.UUID("6f2df576-0504-4645-ae26-6f11d0c0ffee")
_CASE_RE = re.compile(r"CR-[A-Z]\d{2}")
CONCURRENCY = int(os.getenv("OCR_BATCH_CONCURRENCY", "4"))
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".pdf": "application/pdf"}


def _slug(name: str) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in name)
    return re.sub(r"-+", "-", keep).strip("-").lower()


def doc_id_for(folder: str, filename: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"{folder}/{filename}")


def _providers() -> list[AzureReadProvider]:
    provs = [AzureReadProvider(endpoint=os.environ["AZURE_DI_ENDPOINT"],
                               key=os.environ["AZURE_DI_KEY"])]
    ep2, key2 = os.getenv("AZURE_DI_ENDPOINT_2"), os.getenv("AZURE_DI_KEY_2")
    if ep2 and key2:
        provs.append(AzureReadProvider(endpoint=ep2, key=key2))
    return provs


def _doc_to_dict(doc) -> dict:
    return json.loads(doc.model_dump_json())


async def _ocr_folder(folder: Path, provs: list[AzureReadProvider], limit: int | None) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{_slug(folder.name)}.json"
    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    done = {d["file"]: d for d in existing.get("documents", [])}

    images = sorted(p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in _MIME)
    if limit:
        images = images[:limit]
    todo = [p for p in images if p.name not in done]
    print(f"[{folder.name}] {len(images)} ảnh, {len(todo)} cần OCR (đã có {len(done)})")

    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(idx: int, img: Path) -> tuple[str, dict | None]:
        async with sem:
            prov = provs[idx % len(provs)]
            did = doc_id_for(folder.name, img.name)
            try:
                doc = await prov.extract(img.read_bytes(),
                                         mime_type=_MIME[img.suffix.lower()], document_id=did)
            except Exception as e:  # noqa: BLE001
                print(f"  ! LỖI {img.name}: {e}")
                return img.name, None
            nlines = sum(len(p.lines) for p in doc.pages)
            print(f"  ✓ {img.name}: {len(doc.pages)} trang, {nlines} dòng")
            return img.name, _doc_to_dict(doc)

    results = await asyncio.gather(*(one(i, p) for i, p in enumerate(todo)))
    for name, d in results:
        if d is not None:
            done[name] = {"file": name, **d}

    all_text = " ".join(d.get("full_text", "") for d in done.values())
    m = _CASE_RE.search(all_text)
    case_id = m.group(0) if m else existing.get("case_id")
    payload = {"folder": folder.name, "case_id": case_id,
               "documents": [done[k] for k in sorted(done)]}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{folder.name}] → {out_path.name}  case_id={case_id}")
    return payload


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="giới hạn số ảnh/thư mục")
    ap.add_argument("--folder", default=None, help="chỉ chạy 1 thư mục theo tên")
    args = ap.parse_args()

    if not os.getenv("AZURE_DI_ENDPOINT") or not os.getenv("AZURE_DI_KEY"):
        raise SystemExit("Thiếu AZURE_DI_ENDPOINT/AZURE_DI_KEY (nạp .env trước).")
    provs = _providers()
    folders = [d for d in sorted(DOCS_ROOT.iterdir())
               if d.is_dir() and "mock_" not in d.name]
    if args.folder:
        folders = [d for d in folders if d.name == args.folder]

    index = {}
    for folder in folders:
        payload = await _ocr_folder(folder, provs, args.limit)
        index[_slug(folder.name)] = {"folder": folder.name, "case_id": payload["case_id"],
                                     "documents": len(payload["documents"])}
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nIndex:", json.dumps(index, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
