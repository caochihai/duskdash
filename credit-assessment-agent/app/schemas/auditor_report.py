from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.common import CriterionStatus, Issue, JsonValue, StrictModel
from app.schemas.input_ocr_bundle import DocumentType


class ReviewStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNREADABLE = "UNREADABLE"
    MISSING = "MISSING"


class ScanStatus(StrEnum):
    REVIEWED = "REVIEWED"
    UNREADABLE = "UNREADABLE"
    MISSING = "MISSING"


class PageConclusion(StrEnum):
    NO_ISSUE_FOUND = "NO_ISSUE_FOUND"
    ISSUE_FOUND = "ISSUE_FOUND"
    UNREADABLE = "UNREADABLE"
    MISSING = "MISSING"


class DocumentManifestSummary(StrictModel):
    expected_documents: int = Field(ge=1)
    expected_pages: int = Field(ge=1)
    document_ids: list[str] = Field(min_length=1)


class DocumentReviewed(StrictModel):
    document_id: str
    document_type: DocumentType
    pages_expected: int = Field(ge=1)
    pages_reviewed: int = Field(ge=0)
    review_status: ReviewStatus


class PageAudit(StrictModel):
    document_id: str
    page_number: int = Field(ge=1)
    scan_status: ScanStatus
    issues_on_page: list[str] = Field(default_factory=list)
    page_conclusion: PageConclusion


class CriterionResult(StrictModel):
    criterion_id: str
    criterion_name: str
    status: CriterionStatus
    evidence_refs: list[str] = Field(default_factory=list)
    notes: str = ""


class CriterionResults(StrictModel):
    hard_stop: list[CriterionResult] = Field(min_length=1)
    cic: list[CriterionResult] = Field(min_length=1)
    financial_logic: list[CriterionResult] = Field(min_length=1)
    cross_check: list[CriterionResult] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_empty_status(self) -> "CriterionResults":
        for group in (self.hard_stop, self.cic, self.financial_logic, self.cross_check):
            for criterion in group:
                if criterion.status is None:
                    raise ValueError("unchecked criteria must be UNKNOWN, never empty")
        return self


class ExtractedData(StrictModel):
    declared_monthly_income: float | None = None
    recognized_monthly_income: float | None = None
    existing_monthly_debt_service: float | None = None
    proposed_monthly_debt_service: float | None = None
    dti_percent: float | None = None
    cfads: float | None = None
    total_debt_service: float | None = None
    dscr: float | None = None
    highest_cic_group: int | None = Field(default=None, ge=1, le=5)
    maximum_dpd: int | None = Field(default=None, ge=0)
    recent_dpd: int | None = Field(default=None, ge=0)
    number_of_credit_institutions: int | None = Field(default=None, ge=0)
    collateral: dict[str, JsonValue] | None = None


class ScanCompleteness(StrictModel):
    expected_documents: int = Field(ge=1)
    reviewed_documents: int = Field(ge=0)
    expected_pages: int = Field(ge=1)
    reviewed_pages: int = Field(ge=0)
    unreadable_pages: int = Field(ge=0)
    missing_pages: int = Field(ge=0)
    four_layers_completed: bool


class AuditorReport(StrictModel):
    schema_version: str = "1.0"
    case_id: str
    customer_id: str
    agent_id: str
    run_id: str
    document_manifest_summary: DocumentManifestSummary
    documents_reviewed: list[DocumentReviewed]
    page_audit: list[PageAudit]
    criterion_results: CriterionResults
    extracted_data: ExtractedData
    issues_found: list[Issue]
    scan_completeness: ScanCompleteness
    scan_completeness_confirmation: bool

    @model_validator(mode="after")
    def validate_issue_ids_and_page_refs(self) -> "AuditorReport":
        issue_ids = [issue.issue_id for issue in self.issues_found]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("issue_id values must be unique")
        known = set(issue_ids)
        for page in self.page_audit:
            unknown = set(page.issues_on_page) - known
            if unknown:
                raise ValueError(f"page audit references unknown issues: {sorted(unknown)}")
        return self

