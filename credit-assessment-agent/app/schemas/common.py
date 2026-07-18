from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IssueCategory(StrEnum):
    HARD_STOP = "HARD_STOP"
    CIC_RED_FLAG = "CIC_RED_FLAG"
    FINANCIAL_LOGIC_FAIL = "FINANCIAL_LOGIC_FAIL"
    CROSS_CHECK_MISMATCH = "CROSS_CHECK_MISMATCH"
    MINOR_DISCREPANCY = "MINOR_DISCREPANCY"
    MISSING_DOCUMENT = "MISSING_DOCUMENT"
    PRE_DISBURSEMENT_CONDITION = "PRE_DISBURSEMENT_CONDITION"
    POLICY_REVIEW_REQUIRED = "POLICY_REVIEW_REQUIRED"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CriterionStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ProcessingStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INTERNAL_RETRY_REQUIRED = "INTERNAL_RETRY_REQUIRED"
    MANUAL_PROCESSING_REQUIRED = "MANUAL_PROCESSING_REQUIRED"


class Decision(StrEnum):
    REJECT = "REJECT"
    PENDING = "PENDING"
    APPROVE_WITH_CONDITIONS = "APPROVE_WITH_CONDITIONS"
    APPROVE = "APPROVE"


class Evidence(StrictModel):
    source: str = Field(min_length=1)
    value: JsonValue
    unit: str | None = None
    source_excerpt: str | None = None


class IssueLocation(StrictModel):
    document_id: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    field_name: str | None = None
    source_filename: str | None = None
    document_title: str | None = None


class Issue(StrictModel):
    issue_id: str = Field(min_length=1)
    category: IssueCategory
    severity: Severity
    location: IssueLocation
    description: str = Field(min_length=1)
    why_it_is_an_issue: str | None = None
    business_impact: str | None = None
    evidence: list[Evidence] = Field(min_length=1)
    difference_amount: float | None = None
    difference_percent: float | None = None
    requires_customer_action: bool
    suggested_customer_action: str | None = None
    resolution_steps: list[str] = Field(default_factory=list)
    next_step_after_resolution: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
