from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, Field, model_validator

from app.schemas.common import JsonValue, StrictModel
from app.schemas.input_ocr_bundle import (
    DocumentManifest,
    DocumentType,
    PageQualityFlag,
    PolicyContext,
)


class ExtractedTable(StrictModel):
    """A table already extracted by the upstream document extraction service."""

    name: str | None = None
    rows: list[list[JsonValue]] = Field(default_factory=list)


class ExtractedPage(StrictModel):
    """Text/data block with enough provenance to trace a finding to its source page."""

    document_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    text: str = Field(validation_alias=AliasChoices("text", "ocr_text"))
    tables: list[ExtractedTable] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tables", "ocr_tables"),
    )
    extracted_fields: dict[str, JsonValue] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("extracted_fields", "ocr_fields"),
    )
    extraction_confidence: float = Field(
        ge=0,
        le=1,
        validation_alias=AliasChoices("extraction_confidence", "ocr_confidence"),
    )
    quality_flag: PageQualityFlag = Field(
        validation_alias=AliasChoices("quality_flag", "page_quality_flag")
    )
    block_id: str | None = None

    # Compatibility properties let the existing analysis modules migrate without
    # reintroducing PDF/image/OCR responsibilities into the public v2 contract.
    @property
    def ocr_text(self) -> str:
        return self.text

    @property
    def ocr_tables(self) -> list[ExtractedTable]:
        return self.tables

    @property
    def ocr_fields(self) -> dict[str, JsonValue]:
        return self.extracted_fields

    @property
    def ocr_confidence(self) -> float:
        return self.extraction_confidence

    @property
    def page_quality_flag(self) -> PageQualityFlag:
        return self.quality_flag


class ExtractedCaseBundle(StrictModel):
    """Public v2 input: normalized text/data only, never PDF/image bytes."""

    schema_version: Literal["2.0"] = "2.0"
    case_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    product_code: str | None = None
    source_system: str | None = None
    document_manifest: DocumentManifest
    pages: list[ExtractedPage] = Field(
        default_factory=list,
        validation_alias=AliasChoices("pages", "content_blocks", "ocr_pages"),
    )
    policy_context: PolicyContext | None = None

    @model_validator(mode="after")
    def validate_page_references(self) -> "ExtractedCaseBundle":
        manifest = {item.document_id: item.page_count for item in self.document_manifest.documents}
        seen: set[tuple[str, int]] = set()
        for page in self.pages:
            if page.document_id not in manifest:
                raise ValueError(f"page references unknown document_id: {page.document_id}")
            if page.page_number > manifest[page.document_id]:
                raise ValueError(
                    f"page_number {page.page_number} exceeds manifest count for {page.document_id}"
                )
            key = (page.document_id, page.page_number)
            if key in seen:
                raise ValueError(f"duplicate extracted page: {page.document_id}/{page.page_number}")
            seen.add(key)
        return self

    @property
    def ocr_pages(self) -> list[ExtractedPage]:
        """Temporary internal compatibility alias; not part of the v2 JSON contract."""

        return self.pages


AssessmentInput = ExtractedCaseBundle


__all__ = [
    "AssessmentInput",
    "DocumentManifest",
    "DocumentType",
    "ExtractedCaseBundle",
    "ExtractedPage",
    "ExtractedTable",
    "PageQualityFlag",
    "PolicyContext",
]
