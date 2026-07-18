from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.common import (
    Decision,
    Issue,
    IssueCategory,
    ProcessingStatus,
    Severity,
    StrictModel,
)


class MissingReason(StrEnum):
    MISSING = "MISSING"
    UNREADABLE = "UNREADABLE"
    INCOMPLETE_PAGES = "INCOMPLETE_PAGES"


class OutputScanCompleteness(StrictModel):
    expected_pages: int = Field(ge=1)
    reviewed_pages: int = Field(ge=0)
    unreadable_pages: int = Field(ge=0)
    missing_pages: int = Field(ge=0)
    four_layers_completed: bool


class KeyFinancialMetrics(StrictModel):
    declared_income: float | None = None
    recognized_income: float | None = None
    dti_percent: float | None = None
    dscr: float | None = None
    cfads: float | None = None
    highest_cic_group: int | None = Field(default=None, ge=1, le=5)
    maximum_dpd: int | None = Field(default=None, ge=0)
    recent_dpd: int | None = Field(default=None, ge=0)
    dti_formula: str | None = None
    dti_operands: dict[str, float] = Field(default_factory=dict)
    dti_decision_eligible: bool = False
    dti_warning: str | None = None
    dti_reported_percent: float | None = None
    dti_source: str | None = None
    dti_source_excerpt: str | None = None
    dti_reconciliation_status: str | None = None
    dscr_formula: str | None = None
    dscr_operands: dict[str, float] = Field(default_factory=dict)
    dscr_decision_eligible: bool = False
    dscr_warning: str | None = None


class MissingOrIncompleteDocument(StrictModel):
    document_type: str
    reason: MissingReason
    impact: str


class CustomerRequest(StrictModel):
    request_id: str
    request: str
    related_issue_ids: list[str]
    priority: Severity


class ApprovalCondition(StrictModel):
    condition: str
    purpose: str


class AuditTrace(StrictModel):
    run_id: str
    agent_prompt_version: str
    policy_version: str
    generated_at: datetime


class GroundingStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    NEEDS_HUMAN_VERIFICATION = "NEEDS_HUMAN_VERIFICATION"
    INVALID_SOURCE_REFERENCE = "INVALID_SOURCE_REFERENCE"


class FindingType(StrEnum):
    POLICY_BLOCKER = "POLICY_BLOCKER"
    FINANCIAL_ERROR = "FINANCIAL_ERROR"
    CONTRADICTION = "CONTRADICTION"
    RISK_SIGNAL = "RISK_SIGNAL"
    DATA_QUALITY_ERROR = "DATA_QUALITY_ERROR"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    PRE_DISBURSEMENT_CONDITION = "PRE_DISBURSEMENT_CONDITION"
    REQUIRES_POLICY_CLASSIFICATION = "REQUIRES_POLICY_CLASSIFICATION"


class FindingSource(StrictModel):
    document_id: str
    source_filename: str
    document_title: str
    page_number: int = Field(ge=1)
    field_name: str | None = None
    source_excerpt: str
    ocr_confidence: float = Field(ge=0, le=1)


class ActionableFinding(StrictModel):
    finding_id: str
    category: IssueCategory
    severity: Severity
    finding_type: FindingType
    what_is_wrong: str
    why_it_is_an_issue: str
    business_impact: str
    sources: list[FindingSource] = Field(min_length=1)
    grounding_status: GroundingStatus
    decision_effect: str
    customer_action: str | None = None
    internal_action: str
    next_step_after_fix: str


class BankerView(StrictModel):
    decision: Decision | None
    can_submit_for_approval: bool
    headline: str
    total_findings: int = Field(ge=0)
    critical_findings: int = Field(ge=0)
    high_findings: int = Field(ge=0)
    verified_findings: int = Field(ge=0)
    findings_needing_human_verification: int = Field(ge=0)
    findings: list[ActionableFinding]
    one_time_customer_request_list: list[str]
    internal_next_steps: list[str]
    required_document_checklist_status: str


class AssessmentReport(StrictModel):
    schema_version: str = "1.0"
    case_id: str
    customer_id: str
    processing_status: ProcessingStatus
    scan_completeness: OutputScanCompleteness
    decision_recommendation: Decision | None
    decision_summary: str
    key_financial_metrics: KeyFinancialMetrics
    all_issues: list[Issue]
    missing_or_incomplete_documents: list[MissingOrIncompleteDocument]
    consolidated_customer_requests: list[CustomerRequest]
    approval_conditions_if_applicable: list[ApprovalCondition]
    human_review_required: bool = True
    human_review_focus: list[str]
    banker_view: BankerView | None = None
    audit_trace: AuditTrace

    @model_validator(mode="after")
    def keep_processing_and_credit_status_separate(self) -> "AssessmentReport":
        if self.processing_status != ProcessingStatus.COMPLETE and self.decision_recommendation is not None:
            raise ValueError("credit decision must be null until processing is COMPLETE")
        if self.processing_status == ProcessingStatus.COMPLETE and self.decision_recommendation is None:
            raise ValueError("completed processing requires a credit decision recommendation")
        if any(item.reason == MissingReason.UNREADABLE for item in self.missing_or_incomplete_documents):
            unreadable_issue_ids = {
                issue.issue_id
                for issue in self.all_issues
                if "unreadable" in issue.description.lower() or "ocr" in issue.description.lower()
            }
            if unreadable_issue_ids:
                raise ValueError("technical OCR errors must not be represented as customer issues")
        return self
