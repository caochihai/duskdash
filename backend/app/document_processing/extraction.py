"""Small deterministic field extractor for the offline pipeline."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.document_processing.models import ExtractedFieldResult, PageResult

_INCOME = re.compile(
    r"(?:monthly\s+income|salary|gross\s+pay|luong|lương)\s*[:=]?\s*([0-9][0-9., ]*)",
    re.IGNORECASE,
)


class DeterministicFieldExtractor:
    async def extract(self, pages: tuple[PageResult, ...]) -> tuple[ExtractedFieldResult, ...]:
        results: list[ExtractedFieldResult] = []
        for page in pages:
            match = _INCOME.search(page.text_content)
            if match is None:
                continue
            raw = match.group(1).strip()
            try:
                amount = _parse_amount(raw)
            except InvalidOperation:
                continue
            results.append(
                ExtractedFieldResult(
                    field_name="monthly_income",
                    value_type="NUMBER",
                    ocr_value_text=raw,
                    normalized_value_text=format(amount, "f"),
                    value_number=amount,
                    page_number=page.page_number,
                    confidence=page.ocr_confidence,
                    source_text=match.group(0),
                )
            )
        return tuple(results)


def _parse_amount(value: str) -> Decimal:
    compact = value.replace(" ", "")
    if compact.count(",") == 1 and compact.count(".") == 0:
        tail = compact.rsplit(",", 1)[1]
        compact = compact.replace(",", ".") if len(tail) <= 2 else compact.replace(",", "")
    else:
        compact = compact.replace(",", "")
    return Decimal(compact)
