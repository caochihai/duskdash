from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.schemas.input_ocr_bundle import OCRBundle, OCRPage


@dataclass(frozen=True)
class GroundedDTI:
    recognized_monthly_income: float
    existing_monthly_debt_service: float
    proposed_monthly_debt_service: float
    recalculated_percent: float
    reported_percent: float
    document_id: str
    page_number: int
    source_filename: str
    source_excerpt: str


def extract_grounded_dti(bundle: OCRBundle) -> GroundedDTI | None:
    """Extract a DTI only when operands and reported result reconcile on one page."""

    manifest = {item.document_id: item for item in bundle.document_manifest.documents}
    for page in bundle.ocr_pages:
        candidate = _extract_page_dti(page)
        if candidate is None:
            continue
        income, existing, proposed, reported, excerpt = candidate
        recalculated = round((existing + proposed) / income * 100, 4)
        if abs(recalculated - reported) > 0.25:
            continue
        item = manifest[page.document_id]
        filename = item.source_filename or str(page.ocr_fields.get("source_filename") or page.document_id)
        return GroundedDTI(
            recognized_monthly_income=income,
            existing_monthly_debt_service=existing,
            proposed_monthly_debt_service=proposed,
            recalculated_percent=recalculated,
            reported_percent=reported,
            document_id=page.document_id,
            page_number=page.page_number,
            source_filename=filename,
            source_excerpt=excerpt,
        )
    return None


def _extract_page_dti(page: OCRPage) -> tuple[float, float, float, float, str] | None:
    lines = [line.strip() for line in page.ocr_text.splitlines() if line.strip()]
    normalized = [_normalize(line) for line in lines]
    income_index = _find_index(normalized, _is_total_income_label)
    existing_index = _find_index(normalized, lambda line: "nghia vu sau tai cau truc" in line)
    proposed_index = _find_index(normalized, lambda line: "khoan tra no moi du kien" in line)
    dti_index = _find_index(
        normalized,
        lambda line: "dti sau tai cau truc" in line or "ty le dti sau de xuat" in line,
    )
    if None in {income_index, existing_index, proposed_index, dti_index}:
        return None
    income = _read_value(lines, income_index, amount=True)
    existing = _read_value(lines, existing_index, amount=True)
    proposed = _read_value(lines, proposed_index, amount=True)
    reported = _read_value(lines, dti_index, amount=False)
    if any(value is None for value in (income, existing, proposed, reported)) or not income:
        return None
    indices = [income_index, existing_index, proposed_index, dti_index]
    excerpt_lines: list[str] = []
    for index in indices:
        excerpt_lines.extend(lines[index : min(len(lines), index + 2)])
    excerpt = " | ".join(dict.fromkeys(excerpt_lines))[:700]
    return income, existing, proposed, reported, excerpt


def _is_total_income_label(line: str) -> bool:
    if "tong thu nhap chap nhan" in line:
        return True
    return line.rstrip(": ") == "thu nhap chap nhan"


def _find_index(lines: list[str], predicate) -> int | None:
    return next((index for index, line in enumerate(lines) if predicate(line)), None)


def _read_value(lines: list[str], label_index: int, *, amount: bool) -> float | None:
    label = lines[label_index]
    candidates = []
    if ":" in label:
        candidates.append(label.split(":", 1)[1])
    candidates.extend(lines[label_index + 1 : label_index + 3])
    for candidate in candidates:
        match = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)", candidate)
        if not match:
            continue
        value = float(match.group(1).replace(",", "."))
        if not amount:
            return value
        unit_text = _normalize(candidate)
        if "ty" in unit_text and "trieu" not in unit_text:
            return value * 1_000_000_000
        if "trieu" in unit_text:
            return value * 1_000_000
        return value
    return None


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("đ", "d"))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized).strip()
