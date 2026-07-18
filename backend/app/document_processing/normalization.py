"""Non-destructive normalization; corrected human values are never overwritten."""

from __future__ import annotations

from decimal import Decimal

from app.document_processing.models import ExtractedFieldResult


class FieldNormalizer:
    async def normalize(
        self, fields: tuple[ExtractedFieldResult, ...]
    ) -> tuple[ExtractedFieldResult, ...]:
        normalized: list[ExtractedFieldResult] = []
        for field in fields:
            number = field.value_number
            text = field.normalized_value_text.strip() if field.normalized_value_text else None
            if number is not None:
                number = number.quantize(Decimal("0.0001"))
                text = format(number, "f")
            normalized.append(field.model_copy(update={"value_number": number, "normalized_value_text": text}))
        return tuple(normalized)
