from __future__ import annotations

import re
from datetime import date
from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.common import JsonValue, StrictModel


class DocumentType(StrEnum):
    CCCD = "CCCD"
    HOP_DONG_LAO_DONG = "HOP_DONG_LAO_DONG"
    BANG_LUONG = "BANG_LUONG"
    SAO_KE_NGAN_HANG = "SAO_KE_NGAN_HANG"
    BAO_CAO_CIC = "BAO_CAO_CIC"
    TO_KHAI_THUE = "TO_KHAI_THUE"
    BAO_CAO_TAI_CHINH = "BAO_CAO_TAI_CHINH"
    SO_SACH_NOI_BO = "SO_SACH_NOI_BO"
    HOA_DON_DAU_VAO = "HOA_DON_DAU_VAO"
    HOA_DON_DAU_RA = "HOA_DON_DAU_RA"
    HOP_DONG_KINH_TE = "HOP_DONG_KINH_TE"
    TAI_SAN_BAO_DAM = "TAI_SAN_BAO_DAM"
    GCN_QSDD = "GCN_QSDD"
    DANG_KY_KINH_DOANH = "DANG_KY_KINH_DOANH"
    GIAY_PHEP_CHUYEN_NGANH = "GIAY_PHEP_CHUYEN_NGANH"
    KHAC = "KHAC"


class PageQualityFlag(StrEnum):
    OK = "OK"
    BLURRY = "BLURRY"
    ROTATED = "ROTATED"
    BLANK = "BLANK"
    UNREADABLE = "UNREADABLE"


class OCRTable(StrictModel):
    name: str | None = None
    rows: list[list[JsonValue]] = Field(default_factory=list)


class DocumentManifestItem(StrictModel):
    document_id: str = Field(min_length=1)
    document_type: DocumentType
    page_count: int = Field(ge=1)
    sha256: str
    source_filename: str | None = None
    document_title: str | None = None

    @model_validator(mode="after")
    def validate_sha256(self) -> "DocumentManifestItem":
        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.sha256):
            raise ValueError("sha256 must contain exactly 64 hexadecimal characters")
        return self


class DocumentManifest(StrictModel):
    total_documents: int = Field(ge=1)
    total_pages: int = Field(ge=1)
    documents: list[DocumentManifestItem] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_totals(self) -> "DocumentManifest":
        if self.total_documents != len(self.documents):
            raise ValueError("total_documents must equal len(documents)")
        if self.total_pages != sum(item.page_count for item in self.documents):
            raise ValueError("total_pages must equal the sum of document page_count values")
        ids = [item.document_id for item in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("document_id values must be unique")
        return self


class OCRPage(StrictModel):
    document_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    ocr_text: str
    ocr_tables: list[OCRTable] = Field(default_factory=list)
    ocr_fields: dict[str, JsonValue] = Field(default_factory=dict)
    ocr_confidence: float = Field(ge=0, le=1)
    page_quality_flag: PageQualityFlag


class PolicyContext(StrictModel):
    """Bank-approved inputs that the document agent is not allowed to invent."""

    policy_version: str = Field(min_length=1)
    policy_id: str | None = None
    effective_from: date | None = None
    required_document_types: list[DocumentType] = Field(min_length=1)
    verified_metric_names: list[str] = Field(default_factory=list)
    action_rule_sections: dict[str, str] = Field(default_factory=dict)


class OCRBundle(StrictModel):
    case_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    document_manifest: DocumentManifest
    ocr_pages: list[OCRPage] = Field(default_factory=list)
    policy_context: PolicyContext | None = None

    @model_validator(mode="after")
    def validate_page_references(self) -> "OCRBundle":
        manifest = {item.document_id: item.page_count for item in self.document_manifest.documents}
        seen: set[tuple[str, int]] = set()
        for page in self.ocr_pages:
            if page.document_id not in manifest:
                raise ValueError(f"ocr page references unknown document_id: {page.document_id}")
            if page.page_number > manifest[page.document_id]:
                raise ValueError(
                    f"page_number {page.page_number} exceeds manifest count for {page.document_id}"
                )
            key = (page.document_id, page.page_number)
            if key in seen:
                raise ValueError(f"duplicate OCR page: {page.document_id}/{page.page_number}")
            seen.add(key)
        return self
