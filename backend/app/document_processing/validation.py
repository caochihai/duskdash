"""Conservative field/classification checks that create review issues."""

from __future__ import annotations

from decimal import Decimal

from app.document_processing.classification import Classification
from app.document_processing.models import ExtractedFieldResult, IssueResult, PageResult


class FieldValidator:
    async def validate(
        self,
        *,
        pages: tuple[PageResult, ...],
        fields: tuple[ExtractedFieldResult, ...],
        classification: Classification,
    ) -> tuple[IssueResult, ...]:
        issues: list[IssueResult] = []
        if classification.confidence < Decimal("0.75000"):
            issues.append(
                IssueResult(
                    issue_type="LOW_OCR_CONFIDENCE",
                    severity="MEDIUM",
                    title="Document classification needs review",
                    description="The deterministic classifier did not reach the review threshold.",
                )
            )
        if any(page.ocr_confidence < Decimal("0.80000") for page in pages):
            issues.append(
                IssueResult(
                    issue_type="LOW_OCR_CONFIDENCE",
                    severity="MEDIUM",
                    title="OCR confidence below threshold",
                    description="At least one page should be reviewed by a document reviewer.",
                )
            )
        if any(field.value_number is not None and field.value_number < 0 for field in fields):
            issues.append(
                IssueResult(
                    issue_type="INCONSISTENT_FIELD",
                    severity="HIGH",
                    title="Negative financial field",
                    description="A financial field contains an unexpected negative value.",
                )
            )
        return tuple(issues)
