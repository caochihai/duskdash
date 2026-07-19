from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.common import IssueCategory, StrictModel


class ActionType(StrEnum):
    VERIFY_EXTRACTED_SOURCE = "VERIFY_EXTRACTED_SOURCE"
    REQUEST_DOCUMENT = "REQUEST_DOCUMENT"
    VERIFY_IDENTITY = "VERIFY_IDENTITY"
    RECALCULATE = "RECALCULATE"
    CIC_RECHECK = "CIC_RECHECK"
    AML_ESCALATION = "AML_ESCALATION"
    LEGAL_REVIEW = "LEGAL_REVIEW"
    COLLATERAL_REVIEW = "COLLATERAL_REVIEW"
    POLICY_REVIEW = "POLICY_REVIEW"
    STOP_PROCESSING = "STOP_PROCESSING"
    SUBMIT_FOR_APPROVAL = "SUBMIT_FOR_APPROVAL"
    REASSESS = "REASSESS"


class OwnerRole(StrEnum):
    RELATIONSHIP_MANAGER = "RELATIONSHIP_MANAGER"
    CREDIT_APPRAISER = "CREDIT_APPRAISER"
    CREDIT_APPROVER = "CREDIT_APPROVER"
    COMPLIANCE_AML = "COMPLIANCE_AML"
    LEGAL = "LEGAL"
    COLLATERAL_VALUATION = "COLLATERAL_VALUATION"


class RequirementLevel(StrEnum):
    REQUIRED_BY_LAW = "REQUIRED_BY_LAW"
    REQUIRED_BY_BANK_POLICY = "REQUIRED_BY_BANK_POLICY"
    RISK_CONTROL_RECOMMENDED = "RISK_CONTROL_RECOMMENDED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ActionStatus(StrEnum):
    READY_FOR_HUMAN_EXECUTION = "READY_FOR_HUMAN_EXECUTION"
    MANUAL_POLICY_REVIEW_REQUIRED = "MANUAL_POLICY_REVIEW_REQUIRED"


class ActionAudience(StrEnum):
    CUSTOMER = "CUSTOMER"
    INTERNAL = "INTERNAL"
    REGULATORY = "REGULATORY"


class BlockingStage(StrEnum):
    ASSESSMENT = "ASSESSMENT"
    APPROVAL = "APPROVAL"
    DISBURSEMENT = "DISBURSEMENT"
    NONE = "NONE"


class LegalBasis(StrictModel):
    document: str
    article: str
    official_url: str
    effective_from: date
    source_version: str
    last_reviewed_at: date


class BankPolicyBasis(StrictModel):
    policy_id: str
    version: str
    section: str
    effective_from: date


class PolicyActionRule(StrictModel):
    rule_id: str
    version: str
    effective_from: date
    effective_to: date | None = None
    issue_category: IssueCategory
    action_type: ActionType
    owner_role: OwnerRole
    requirement_level: RequirementLevel
    audience: ActionAudience
    why_required: str
    legal_basis: list[LegalBasis] = Field(min_length=1)
    required_evidence: list[str] = Field(min_length=1)
    completion_criteria: list[str] = Field(min_length=1)
    blocking_stage: BlockingStage
    next_state_after_completion: str
    requires_bank_policy: bool = False
    priority: int = Field(default=50, ge=1, le=100)

    def is_effective(self, as_of: date) -> bool:
        return self.effective_from <= as_of and (
            self.effective_to is None or as_of <= self.effective_to
        )


class PolicyActionRegistry(StrictModel):
    registry_id: str
    version: str
    jurisdiction: str
    reviewed_at: date
    rules: list[PolicyActionRule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rule_ids(self) -> "PolicyActionRegistry":
        ids = [rule.rule_id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("policy action rule_id values must be unique")
        return self


class RecommendedAction(StrictModel):
    action_id: str
    finding_ids: list[str] = Field(default_factory=list)
    action_type: ActionType
    owner_role: OwnerRole
    requirement_level: RequirementLevel
    action_status: ActionStatus
    audience: ActionAudience
    why_required: str
    legal_basis: list[LegalBasis]
    bank_policy_basis: list[BankPolicyBasis]
    required_evidence: list[str]
    completion_criteria: list[str]
    blocking_stage: BlockingStage
    priority: int = Field(ge=1, le=100)
    next_state_after_completion: str
    requires_human_confirmation: bool = True
    source_rule_id: str
    source_rule_version: str


class ActionPlan(StrictModel):
    registry_id: str
    registry_version: str
    evaluated_as_of: date
    manual_policy_review_required: bool
    next_actions: list[RecommendedAction]
    customer_actions: list[RecommendedAction]
    internal_actions: list[RecommendedAction]
    regulatory_escalations: list[RecommendedAction]
