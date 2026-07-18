from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
TITLE_MARKERS = (
    "BAO CAO",
    "GIAY CHUNG NHAN",
    "PHIEU",
    "HOP DONG",
    "CHUNG THU",
    "SAO KE",
    "TO KHAI",
    "NGHI QUYET",
    "BANG",
    "DON ",
)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").upper()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_value).upper()


def infer_document_title(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 4]
    for line in lines[:30]:
        normalized = normalize_search_text(line)
        if any(marker in normalized for marker in TITLE_MARKERS):
            return line[:180]
    return lines[0][:180] if lines else "Không xác định được tiêu đề tài liệu"


def infer_document_type(text: str) -> str:
    normalized = normalize_search_text(text[:8000])
    rules = (
        (("CAN CUOC CONG DAN", "CCCD"), "CCCD"),
        (("HOP DONG LAO DONG",), "HOP_DONG_LAO_DONG"),
        (("BANG LUONG", "PHIEU LUONG"), "BANG_LUONG"),
        (("SAO KE TAI KHOAN",), "SAO_KE_NGAN_HANG"),
        (("BAO CAO CIC", "THONG TIN TIN DUNG"), "BAO_CAO_CIC"),
        (("TO KHAI VAT", "TO KHAI THUE"), "TO_KHAI_THUE"),
        (("BAO CAO TAI CHINH", "BANG CAN DOI KE TOAN"), "BAO_CAO_TAI_CHINH"),
        (("SO SACH NOI BO", "SO CHI TIET"), "SO_SACH_NOI_BO"),
        (("HOA DON DAU VAO",), "HOA_DON_DAU_VAO"),
        (("HOA DON DAU RA",), "HOA_DON_DAU_RA"),
        (("HOP DONG MUA BAN", "HOP DONG KINH TE"), "HOP_DONG_KINH_TE"),
        (("CHUNG THU THAM DINH GIA", "TAI SAN BAO DAM"), "TAI_SAN_BAO_DAM"),
        (("GIAY CHUNG NHAN QUYEN SU DUNG DAT", "GCN QSDD"), "GCN_QSDD"),
        (("DANG KY DOANH NGHIEP",), "DANG_KY_KINH_DOANH"),
        (("GIAY PHEP",), "GIAY_PHEP_CHUYEN_NGANH"),
    )
    for needles, document_type in rules:
        if any(needle in normalized for needle in needles):
            return document_type
    return "KHAC"


class EasyOCREngine:
    def __init__(self, cache_dir: Path) -> None:
        try:
            import easyocr
        except ImportError as exc:
            raise SystemExit("easyocr is not installed; install project extra [ocr]") from exc
        self._reader = easyocr.Reader(["vi", "en"], gpu=False, verbose=False)
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def image_text(self, path: Path) -> tuple[str, float]:
        import cv2
        import numpy as np

        cache_path = self._cache_dir / f"{sha256(path)}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return str(cached["text"]), float(cached["confidence"])

        # cv2.imread cannot open Unicode-heavy Windows paths; imdecode can.
        image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return "", 0.0
        results = self._reader.readtext(image, detail=1, paragraph=False)
        text = "\n".join(str(item[1]) for item in results)
        confidences = [float(item[2]) for item in results]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        cache_path.write_text(
            json.dumps({"text": text, "confidence": confidence}, ensure_ascii=False),
            encoding="utf-8",
        )
        return text, confidence


def pdf_pages(path: Path) -> list[tuple[str, float]]:
    from pypdf import PdfReader

    pages: list[tuple[str, float]] = []
    for page in PdfReader(str(path)).pages:
        text = page.extract_text() or ""
        pages.append((text, 1.0 if text.strip() else 0.0))
    return pages


def build_bundle(input_dir: Path, engine: EasyOCREngine | None) -> dict:
    files = sorted(
        [path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES | {".pdf"}],
        key=lambda path: path.name.casefold(),
    )
    if not files:
        raise SystemExit(f"No PDF/image files found in {input_dir}")

    documents: list[dict] = []
    pages: list[dict] = []
    for index, path in enumerate(files, start=1):
        document_id = f"DOC-{index:03d}"
        if path.suffix.lower() == ".pdf":
            extracted = pdf_pages(path)
        elif engine is not None:
            extracted = [engine.image_text(path)]
        else:
            sidecar = path.with_suffix(path.suffix + ".txt")
            extracted = [(sidecar.read_text(encoding="utf-8") if sidecar.exists() else "", 1.0)]

        combined_text = "\n".join(item[0] for item in extracted)
        documents.append(
            {
                "document_id": document_id,
                "document_type": infer_document_type(combined_text),
                "page_count": len(extracted),
                "sha256": sha256(path),
                "source_filename": path.name,
                "document_title": infer_document_title(combined_text),
            }
        )
        for page_number, (text, confidence) in enumerate(extracted, start=1):
            pages.append(
                {
                    "document_id": document_id,
                    "page_number": page_number,
                    "ocr_text": text,
                    "ocr_tables": [],
                    "ocr_fields": {"source_filename": path.name},
                    "ocr_confidence": round(max(0.0, min(confidence, 1.0)), 6),
                    "page_quality_flag": "OK" if text.strip() else "UNREADABLE",
                }
            )

    identity = slugify(input_dir.name)
    return {
        "case_id": f"ACTUAL-{identity}",
        "customer_id": identity,
        "document_manifest": {
            "total_documents": len(documents),
            "total_pages": sum(item["page_count"] for item in documents),
            "documents": documents,
        },
        "ocr_pages": pages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a folder of PDF/images to an OCR Bundle JSON")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--easyocr", action="store_true", help="OCR image files locally with EasyOCR")
    args = parser.parse_args()

    engine = EasyOCREngine(args.output.parent / ".ocr-cache") if args.easyocr else None
    bundle = build_bundle(args.input_dir, engine)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.schemas.input_ocr_bundle import OCRBundle

    validated = OCRBundle.model_validate(bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        validated.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "documents": validated.document_manifest.total_documents,
                "pages": validated.document_manifest.total_pages,
                "unreadable": sum(page.page_quality_flag == "UNREADABLE" for page in validated.ocr_pages),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
