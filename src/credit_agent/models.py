"""Typed contracts for the standalone SME Credit Agent.

The models deliberately make analysis sections nullable.  That lets an early
``NEEDS_INFO`` or ``SYSTEM_EXCEPTION`` response remain schema-valid without
inventing zeroes for data that was never retrieved.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_validator,
    model_validator,
)


DecimalValue = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {"type": "string", "format": "decimal", "pattern": r"^-?\d+(?:\.\d+)?$"},
        mode="serialization",
    ),
]

POSITIVE_DECIMAL_PATTERN = r"^(?:0*(?:[1-9]\d*)(?:\.\d+)?|0*\.\d*[1-9]\d*)$"
NON_NEGATIVE_DECIMAL_PATTERN = r"^(?:\d+(?:\.\d*)?|\.\d+)$"
UNIT_INTERVAL_DECIMAL_PATTERN = r"^(?:0(?:\.\d+)?|1(?:\.0+)?)$"

PositiveDecimalValue = Annotated[
    DecimalValue,
    Field(gt=0),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number", "exclusiveMinimum": 0},
                {"type": "string", "pattern": POSITIVE_DECIMAL_PATTERN},
            ]
        },
        mode="validation",
    ),
    WithJsonSchema(
        {"type": "string", "format": "decimal", "pattern": POSITIVE_DECIMAL_PATTERN},
        mode="serialization",
    ),
]

NonNegativeDecimalValue = Annotated[
    DecimalValue,
    Field(ge=0),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number", "minimum": 0},
                {"type": "string", "pattern": NON_NEGATIVE_DECIMAL_PATTERN},
            ]
        },
        mode="validation",
    ),
    WithJsonSchema(
        {
            "type": "string",
            "format": "decimal",
            "pattern": NON_NEGATIVE_DECIMAL_PATTERN,
        },
        mode="serialization",
    ),
]

UnitIntervalDecimalValue = Annotated[
    DecimalValue,
    Field(ge=0, le=1),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number", "minimum": 0, "maximum": 1},
                {"type": "string", "pattern": UNIT_INTERVAL_DECIMAL_PATTERN},
            ]
        },
        mode="validation",
    ),
    WithJsonSchema(
        {
            "type": "string",
            "format": "decimal",
            "pattern": UNIT_INTERVAL_DECIMAL_PATTERN,
        },
        mode="serialization",
    ),
]


def _decision_schema_condition(decisions: list[str]) -> dict[str, Any]:
    return {
        "properties": {
            "recommendation": {
                "properties": {"decision": {"enum": decisions}},
                "required": ["decision"],
            }
        },
        "required": ["recommendation"],
    }


def _credit_task_schema_metadata(schema: dict[str, Any]) -> None:
    schema["$comment"] = (
        "Shape-level integration schema. CreditTaskInputV1.model_validate remains "
        "authoritative for cross-field and date invariants."
    )
    schema["x-credit-agent-runtime-invariants"] = [
        "task_type must match credit_request.request_type",
        "as_of_date cannot be in the future",
        "all undeclared fields are rejected",
    ]


def _credit_result_schema_metadata(schema: dict[str, Any]) -> None:
    schema["$comment"] = (
        "Serialization schema with core decision/status/amount conditionals. "
        "CreditAnalysisResultV1.model_validate remains authoritative for evidence "
        "referential integrity and other cross-collection invariants."
    )
    schema["x-credit-agent-runtime-invariants"] = [
        "status must agree with recommendation.decision",
        "positive decisions require amount, tenor, currency and active policy evidence",
        "non-positive decisions cannot carry a recommended amount or tenor",
        "all evidence and policy claim references must resolve",
        "READY requires complete, fresh, conflict-free data with no unresolved risk state",
        "PASS_WITH_CONDITIONS cannot contain missing, blocked, conflict, info-request, or error state",
        "human_approval_required is always true",
    ]
    completed = [
        "READY_FOR_APPROVAL_REVIEW",
        "PASS_WITH_CONDITIONS",
        "MANUAL_REVIEW",
        "NOT_RECOMMENDED",
    ]
    positive = ["READY_FOR_APPROVAL_REVIEW", "PASS_WITH_CONDITIONS"]
    non_positive = [
        "NEEDS_INFO",
        "MANUAL_REVIEW",
        "NOT_RECOMMENDED",
        "SYSTEM_EXCEPTION",
    ]
    schema["allOf"] = [
        {
            "if": _decision_schema_condition(["NEEDS_INFO"]),
            "then": {"properties": {"status": {"const": "NEEDS_INFO"}}},
        },
        {
            "if": _decision_schema_condition(["SYSTEM_EXCEPTION"]),
            "then": {"properties": {"status": {"const": "SYSTEM_EXCEPTION"}}},
        },
        {
            "if": _decision_schema_condition(completed),
            "then": {"properties": {"status": {"const": "COMPLETED"}}},
        },
        {
            "if": _decision_schema_condition(positive),
            "then": {
                "properties": {
                    "recommendation": {
                        "properties": {
                            "recommended_limit": {
                                "type": "string",
                                "pattern": POSITIVE_DECIMAL_PATTERN,
                            },
                            "recommended_tenor_months": {
                                "type": "integer",
                                "exclusiveMinimum": 0,
                            },
                            "currency": {
                                "type": "string",
                                "pattern": "^[A-Z]{3}$",
                            },
                        },
                        "required": [
                            "recommended_limit",
                            "recommended_tenor_months",
                            "currency",
                        ],
                    }
                }
            },
        },
        {
            "if": _decision_schema_condition(non_positive),
            "then": {
                "properties": {
                    "recommendation": {
                        "properties": {
                            "recommended_limit": {"type": "null"},
                            "recommended_tenor_months": {"type": "null"},
                            "currency": {"type": "null"},
                        }
                    }
                }
            },
        },
    ]


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        revalidate_instances="always",
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class TaskType(str, Enum):
    CREDIT_RENEWAL_REVIEW = "CREDIT_RENEWAL_REVIEW"
    CREDIT_LIMIT_REVIEW = "CREDIT_LIMIT_REVIEW"


class RequestType(str, Enum):
    RENEWAL = "RENEWAL"
    LIMIT_REVIEW = "LIMIT_REVIEW"


class ResultStatus(str, Enum):
    COMPLETED = "COMPLETED"
    NEEDS_INFO = "NEEDS_INFO"
    SYSTEM_EXCEPTION = "SYSTEM_EXCEPTION"


class Decision(str, Enum):
    READY_FOR_APPROVAL_REVIEW = "READY_FOR_APPROVAL_REVIEW"
    PASS_WITH_CONDITIONS = "PASS_WITH_CONDITIONS"
    NEEDS_INFO = "NEEDS_INFO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    SYSTEM_EXCEPTION = "SYSTEM_EXCEPTION"


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskCode(str, Enum):
    REV_TXN_MISMATCH = "REV_TXN_MISMATCH"
    PROFIT_CASHFLOW_MISMATCH = "PROFIT_CASHFLOW_MISMATCH"
    RECEIVABLES_SPIKE = "RECEIVABLES_SPIKE"
    INVENTORY_SPIKE = "INVENTORY_SPIKE"
    RECENT_DELINQUENCY = "RECENT_DELINQUENCY"
    RESTRUCTURED_DEBT = "RESTRUCTURED_DEBT"
    LOW_LIMIT_UTILIZATION = "LOW_LIMIT_UTILIZATION"
    HIGH_CUSTOMER_CONCENTRATION = "HIGH_CUSTOMER_CONCENTRATION"
    RELATED_PARTY_FLOW = "RELATED_PARTY_FLOW"
    STALE_COLLATERAL_VALUATION = "STALE_COLLATERAL_VALUATION"
    FINANCIAL_DATA_CONFLICT = "FINANCIAL_DATA_CONFLICT"
    MISSING_LATEST_FINANCIALS = "MISSING_LATEST_FINANCIALS"
    INTERNAL_RATING_OUTSIDE_POLICY = "INTERNAL_RATING_OUTSIDE_POLICY"
    RELATIONSHIP_STATUS_OUTSIDE_POLICY = "RELATIONSHIP_STATUS_OUTSIDE_POLICY"
    OVER_LIMIT_EXPOSURE = "OVER_LIMIT_EXPOSURE"
    COLLATERAL_STATUS_OUTSIDE_POLICY = "COLLATERAL_STATUS_OUTSIDE_POLICY"
    STALE_INTERNAL_RATING = "STALE_INTERNAL_RATING"
    REPEATED_LATE_PAYMENTS = "REPEATED_LATE_PAYMENTS"
    HIGH_INFLOW_VOLATILITY = "HIGH_INFLOW_VOLATILITY"
    LOW_TRANSACTION_CASH_COVERAGE = "LOW_TRANSACTION_CASH_COVERAGE"


class ToolStatus(str, Enum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    NO_DATA = "NO_DATA"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    FORBIDDEN = "FORBIDDEN"


class PolicyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"
    DRAFT = "DRAFT"


class QualityStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    NOT_ASSESSED = "NOT_ASSESSED"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class ConditionStage(str, Enum):
    BEFORE_APPROVAL_REVIEW = "BEFORE_APPROVAL_REVIEW"
    BEFORE_DISBURSEMENT = "BEFORE_DISBURSEMENT"
    ONGOING_COVENANT = "ONGOING_COVENANT"


class CollateralPolicyMode(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CreditRequest(ContractModel):
    model_config = ConfigDict(frozen=True)

    request_type: RequestType
    product_code: str = Field(min_length=1, max_length=64)
    current_limit: NonNegativeDecimalValue
    requested_limit: PositiveDecimalValue
    requested_tenor_months: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    purpose: str = Field(min_length=3, max_length=1000)
    collateral_required: bool


class Permissions(ContractModel):
    model_config = ConfigDict(frozen=True)

    allowed_scopes: frozenset[str] = Field(min_length=1)

    @field_validator("allowed_scopes")
    @classmethod
    def scopes_must_not_be_blank(cls, scopes: frozenset[str]) -> frozenset[str]:
        if any(not scope.strip() for scope in scopes):
            raise ValueError("allowed_scopes cannot contain blank values")
        return scopes


class CreditTaskInputV1(ContractModel):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra=_credit_task_schema_metadata,
    )

    schema_version: Literal["1.0"] = "1.0"
    task_id: str = Field(min_length=1, max_length=128)
    case_id: str = Field(min_length=1, max_length=128)
    task_type: TaskType
    customer_id: str = Field(min_length=1, max_length=128)
    credit_request: CreditRequest
    as_of_date: date
    permissions: Permissions
    plan_id: str | None = Field(default=None, max_length=128)
    plan_version: str | None = Field(default=None, max_length=64)
    attempt: int = Field(default=1, ge=1)
    parent_run_id: str | None = Field(default=None, max_length=128)

    @field_validator("as_of_date")
    @classmethod
    def cutoff_cannot_be_in_the_future(cls, cutoff: date) -> date:
        if cutoff > date.today():
            raise ValueError("as_of_date cannot be in the future")
        return cutoff

    @model_validator(mode="after")
    def request_type_matches_task(self) -> "CreditTaskInputV1":
        expected = {
            TaskType.CREDIT_RENEWAL_REVIEW: RequestType.RENEWAL,
            TaskType.CREDIT_LIMIT_REVIEW: RequestType.LIMIT_REVIEW,
        }[self.task_type]
        if self.credit_request.request_type != expected:
            raise ValueError(
                f"request_type {self.credit_request.request_type.value} does not match "
                f"task_type {self.task_type.value}"
            )
        return self


class CoveragePeriod(ContractModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def valid_order(self) -> "CoveragePeriod":
        if self.end_date < self.start_date:
            raise ValueError("coverage end_date must be on or after start_date")
        return self


T = TypeVar("T")


class ToolEnvelope(ContractModel, Generic[T]):
    task_id: str = Field(min_length=1, max_length=128)
    case_id: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(
        min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"
    )
    tool_run_id: str = Field(min_length=1, max_length=128)
    status: ToolStatus
    source_system: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    )
    source_reference: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9+._:/-]*$",
    )
    as_of_date: date
    retrieved_at: datetime
    coverage_period: CoveragePeriod | None = None
    data: T | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def status_matches_payload(self) -> "ToolEnvelope[T]":
        if self.status in {ToolStatus.OK, ToolStatus.PARTIAL} and self.data is None:
            raise ValueError(f"{self.status.value} tool result requires data")
        if self.status in {
            ToolStatus.NO_DATA,
            ToolStatus.ERROR,
            ToolStatus.TIMEOUT,
            ToolStatus.FORBIDDEN,
        } and self.data is not None:
            raise ValueError(f"{self.status.value} tool result cannot carry data")
        if self.status in {
            ToolStatus.ERROR,
            ToolStatus.TIMEOUT,
            ToolStatus.FORBIDDEN,
        } and not self.error:
            raise ValueError(f"{self.status.value} tool result requires error")
        if self.status in {ToolStatus.OK, ToolStatus.PARTIAL, ToolStatus.NO_DATA} and self.error:
            raise ValueError(f"{self.status.value} tool result cannot carry an error")
        return self


class Customer360Data(ContractModel):
    years_with_bank: NonNegativeDecimalValue
    segment: str
    internal_rating: str
    rating_as_of: date
    total_outstanding: NonNegativeDecimalValue
    average_deposit_balance: NonNegativeDecimalValue
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    relationship_status: str


class FacilityRecord(ContractModel):
    facility_id: str
    product_code: str
    approved_limit: NonNegativeDecimalValue
    outstanding: NonNegativeDecimalValue
    utilization_ratio: NonNegativeDecimalValue
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    maturity_date: date | None = None


class CreditFacilitiesData(ContractModel):
    approved_limit: NonNegativeDecimalValue
    outstanding: NonNegativeDecimalValue
    utilization_ratio: NonNegativeDecimalValue
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    ledger_as_of: date
    facilities: list[FacilityRecord] = Field(default_factory=list)


class RepaymentHistoryData(ContractModel):
    lookback_months: int = Field(ge=0)
    on_time_payment_count: int = Field(ge=0)
    late_payment_count: int = Field(ge=0)
    max_days_past_due: int = Field(ge=0)
    current_days_past_due: int = Field(ge=0)
    restructured_debt: bool
    coverage_period: CoveragePeriod


class TransactionSummaryData(ContractModel):
    average_monthly_inflow: NonNegativeDecimalValue
    average_monthly_outflow: NonNegativeDecimalValue
    inflow_volatility: NonNegativeDecimalValue
    largest_counterparty_share: UnitIntervalDecimalValue
    related_party_flow: bool = False
    coverage_months: int = Field(ge=0)
    coverage_period: CoveragePeriod
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class FinancialStatement(ContractModel):
    statement_id: str
    period_start: date
    period_end: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    unit_multiplier: PositiveDecimalValue = Decimal("1")
    audited: bool
    revenue: DecimalValue | None = None
    gross_profit: DecimalValue | None = None
    ebitda: DecimalValue | None = None
    net_profit: DecimalValue | None = None
    current_assets: DecimalValue | None = None
    inventory: DecimalValue | None = None
    cash: DecimalValue | None = None
    current_liabilities: DecimalValue | None = None
    total_debt: DecimalValue | None = None
    equity: DecimalValue | None = None
    interest_expense: DecimalValue | None = None
    debt_service: DecimalValue | None = None
    operating_cash_flow: DecimalValue | None = None
    capital_expenditure: DecimalValue | None = None
    receivables: DecimalValue | None = None
    payables: DecimalValue | None = None

    @model_validator(mode="after")
    def valid_period(self) -> "FinancialStatement":
        if self.period_end < self.period_start:
            raise ValueError("financial period_end must be on or after period_start")
        return self


class FinancialStatementsData(ContractModel):
    current: FinancialStatement | None
    prior: FinancialStatement | None
    plan: FinancialStatement | None = None

    @model_validator(mode="after")
    def periods_are_comparable(self) -> "FinancialStatementsData":
        if self.current is not None and self.prior is not None:
            if self.current.statement_id == self.prior.statement_id:
                raise ValueError("current and prior statements must have distinct IDs")
            if self.prior.period_end >= self.current.period_start:
                raise ValueError("prior and current financial periods must not overlap")
            if self.current.currency != self.prior.currency:
                raise ValueError("current and prior financial statements must use one currency")
            if self.current.unit_multiplier != self.prior.unit_multiplier:
                raise ValueError("current and prior statements must use one unit multiplier")
        if self.plan is not None and self.current is not None:
            if self.plan.statement_id == self.current.statement_id:
                raise ValueError("plan and current statements must have distinct IDs")
            if self.plan.currency != self.current.currency:
                raise ValueError("plan and current statements must use one currency")
            if self.plan.unit_multiplier != self.current.unit_multiplier:
                raise ValueError("plan and current statements must use one unit multiplier")
        return self


class CalculationContext(ContractModel):
    transaction_summary: TransactionSummaryData | None = None
    facilities: CreditFacilitiesData | None = None
    requested_limit: PositiveDecimalValue
    requested_tenor_months: int
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class MetricValue(ContractModel):
    current: DecimalValue | None = None
    prior: DecimalValue | None = None
    change: DecimalValue | None = None
    plan: DecimalValue | None = None
    plan_variance: DecimalValue | None = None
    unit: str = Field(min_length=1, max_length=64)
    formula: str = Field(min_length=1, max_length=1000)
    input_references: list[str] = Field(min_length=1, max_length=64)

    @field_validator("input_references")
    @classmethod
    def valid_input_references(cls, references: list[str]) -> list[str]:
        if any(not reference or len(reference) > 256 for reference in references):
            raise ValueError(
                "metric input_references must be non-blank and at most 256 characters"
            )
        return references


class FinancialMetricsData(ContractModel):
    formula_version: str = Field(min_length=1)
    metrics: dict[str, MetricValue] = Field(min_length=1, max_length=128)
    missing_inputs: list[str] = Field(default_factory=list)
    non_computable_metrics: list[str] = Field(default_factory=list)


class CollateralSnapshotData(ContractModel):
    collateral_ids: list[str] = Field(min_length=1)
    appraised_value: NonNegativeDecimalValue
    eligible_value: NonNegativeDecimalValue
    valuation_date: date
    coverage_ratio: NonNegativeDecimalValue
    coverage_denominator: PositiveDecimalValue
    coverage_basis: str = Field(min_length=1, max_length=128)
    valuation_status: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class PolicyClause(ContractModel):
    section: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1, max_length=4000)
    claim_ids: set[str] = Field(min_length=1)

    @field_validator("claim_ids")
    @classmethod
    def valid_claim_ids(cls, claim_ids: set[str]) -> set[str]:
        if any(not claim_id or len(claim_id) > 128 for claim_id in claim_ids):
            raise ValueError("claim_ids must contain non-blank values up to 128 characters")
        return claim_ids


class PolicyThresholds(ContractModel):
    repayment_min_coverage_months: int | None = Field(default=None, ge=0)
    transaction_min_coverage_months: int | None = Field(default=None, ge=0)
    max_internal_rating_age_days: int | None = Field(default=None, ge=0)
    max_financial_statement_age_days: int | None = Field(default=None, ge=0)
    max_collateral_valuation_age_days: int | None = Field(default=None, ge=0)
    outstanding_conflict_tolerance_ratio: UnitIntervalDecimalValue | None = None
    revenue_transaction_mismatch_threshold: NonNegativeDecimalValue | None = None
    receivables_growth_threshold: NonNegativeDecimalValue | None = None
    inventory_growth_threshold: NonNegativeDecimalValue | None = None
    recent_delinquency_days: int | None = Field(default=None, ge=0)
    maximum_late_payment_count: int | None = Field(default=None, ge=0)
    maximum_inflow_volatility: NonNegativeDecimalValue | None = None
    minimum_inflow_outflow_ratio: NonNegativeDecimalValue | None = None
    low_limit_utilization_threshold: UnitIntervalDecimalValue | None = None
    high_customer_concentration_threshold: UnitIntervalDecimalValue | None = None
    minimum_dscr: NonNegativeDecimalValue | None = None
    maximum_debt_to_equity: NonNegativeDecimalValue | None = None
    minimum_interest_coverage: NonNegativeDecimalValue | None = None
    minimum_collateral_coverage: NonNegativeDecimalValue | None = None
    collateral_coverage_tolerance_ratio: UnitIntervalDecimalValue | None = None
    maximum_tenor_months: int | None = Field(default=None, gt=0)
    maximum_requested_limit: PositiveDecimalValue | None = None


class CreditPolicyData(ContractModel):
    document_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    status: PolicyStatus
    effective_from: date
    effective_to: date | None = None
    clauses: list[PolicyClause] = Field(min_length=1)
    thresholds: PolicyThresholds
    applicable_task_types: set[TaskType] = Field(min_length=1)
    applicable_product_codes: set[str] = Field(min_length=1)
    applicable_currencies: set[str] = Field(min_length=1)
    applicable_segments: set[str] = Field(min_length=1)
    allowed_internal_ratings: set[str] = Field(min_length=1)
    allowed_relationship_statuses: set[str] = Field(min_length=1)
    allowed_collateral_valuation_statuses: set[str] = Field(min_length=1)
    allowed_collateral_coverage_bases: set[str] = Field(min_length=1)
    require_audited_financial_statements: bool
    collateral_mode: CollateralPolicyMode
    required_metrics: set[str] = Field(default_factory=set)
    not_recommended_flag_codes: set[RiskCode] = Field(default_factory=set)
    condition_flag_codes: set[RiskCode] = Field(default_factory=set)
    not_recommended_metric_names: set[str] = Field(default_factory=set)
    condition_metric_names: set[str] = Field(default_factory=set)
    severity_by_flag: dict[RiskCode, RiskSeverity] = Field(default_factory=dict)
    placeholder_data: bool = False

    @field_validator("applicable_currencies")
    @classmethod
    def validate_policy_currencies(cls, currencies: set[str]) -> set[str]:
        if any(
            value != "*"
            and (len(value) != 3 or not value.isascii() or not value.isupper())
            for value in currencies
        ):
            raise ValueError("applicable_currencies must contain ISO-style codes or '*'")
        return currencies

    @field_validator(
        "applicable_product_codes",
        "applicable_segments",
        "allowed_internal_ratings",
        "allowed_relationship_statuses",
        "allowed_collateral_valuation_statuses",
        "allowed_collateral_coverage_bases",
    )
    @classmethod
    def validate_policy_match_values(cls, values: set[str]) -> set[str]:
        if any(not value or len(value) > 128 for value in values):
            raise ValueError(
                "policy applicability values must be non-blank and at most 128 characters"
            )
        return values

    @model_validator(mode="after")
    def valid_effective_period(self) -> "CreditPolicyData":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        return self

    def is_active_on(self, cutoff: date) -> bool:
        return (
            self.status == PolicyStatus.ACTIVE
            and self.effective_from <= cutoff
            and (self.effective_to is None or cutoff <= self.effective_to)
        )


Customer360Result = ToolEnvelope[Customer360Data]
CreditFacilitiesResult = ToolEnvelope[CreditFacilitiesData]
RepaymentHistoryResult = ToolEnvelope[RepaymentHistoryData]
TransactionSummaryResult = ToolEnvelope[TransactionSummaryData]
FinancialStatementsResult = ToolEnvelope[FinancialStatementsData]
FinancialMetricsResult = ToolEnvelope[FinancialMetricsData]
CollateralSnapshotResult = ToolEnvelope[CollateralSnapshotData]
CreditPolicyResult = ToolEnvelope[CreditPolicyData]


class AgentMetadata(ContractModel):
    agent_id: Literal["credit_agent"] = "credit_agent"
    agent_version: str = Field(min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=128)


class Recommendation(ContractModel):
    decision: Decision
    recommended_limit: PositiveDecimalValue | None = None
    recommended_tenor_months: int | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    human_approval_required: Literal[True] = True
    summary: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids")
    @classmethod
    def valid_evidence_ids(cls, evidence_ids: list[str]) -> list[str]:
        if any(not item or len(item) > 128 for item in evidence_ids):
            raise ValueError("evidence_ids must be non-blank and at most 128 characters")
        return evidence_ids


class RelationshipAnalysis(ContractModel):
    years_with_bank: NonNegativeDecimalValue
    internal_rating: str
    relationship_status: str
    evidence_ids: list[str] = Field(min_length=1)


class FacilityAnalysis(ContractModel):
    current_limit: NonNegativeDecimalValue
    outstanding: NonNegativeDecimalValue
    utilization_ratio: NonNegativeDecimalValue
    currency: str
    evidence_ids: list[str] = Field(min_length=1)


class RepaymentAnalysis(ContractModel):
    lookback_months: int
    late_payment_count: int
    max_days_past_due: int
    current_days_past_due: int
    restructured_debt: bool
    assessment: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1)


class CashflowAnalysis(ContractModel):
    average_monthly_inflow: NonNegativeDecimalValue
    average_monthly_outflow: NonNegativeDecimalValue
    inflow_volatility: NonNegativeDecimalValue
    largest_counterparty_share: UnitIntervalDecimalValue
    currency: str
    assessment: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1)


class CollateralAnalysis(ContractModel):
    eligible_value: NonNegativeDecimalValue
    coverage_ratio: NonNegativeDecimalValue
    valuation_status: str
    currency: str
    evidence_ids: list[str] = Field(min_length=1)


class RiskFlag(ContractModel):
    code: RiskCode
    severity: RiskSeverity
    description: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1)
    requires_clarification: bool


class Condition(ContractModel):
    condition_code: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    description: str = Field(min_length=1, max_length=2000)
    blocking: bool
    stage: ConditionStage
    evidence_ids: list[str] = Field(min_length=1)


class FollowUpQuestion(ContractModel):
    question: str
    why_it_matters: str
    expected_evidence: list[str] = Field(min_length=1)
    blocking_if_unanswered: bool
    evidence_ids: list[str] = Field(default_factory=list)


class PolicyCitation(ContractModel):
    document_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    section: str = Field(min_length=1, max_length=256)
    effective_from: date
    effective_to: date | None = None
    status: PolicyStatus
    claim_ids: list[str] = Field(min_length=1)

    @field_validator("claim_ids")
    @classmethod
    def valid_claim_ids(cls, claim_ids: list[str]) -> list[str]:
        if any(not item or len(item) > 128 for item in claim_ids):
            raise ValueError("claim_ids must be non-blank and at most 128 characters")
        return claim_ids


class Evidence(ContractModel):
    evidence_id: str = Field(min_length=1, max_length=128)
    claim_id: str = Field(min_length=1, max_length=128)
    source_system: str = Field(min_length=1, max_length=128)
    source_reference: str = Field(min_length=1, max_length=256)
    as_of_date: date
    fact: str = Field(min_length=1, max_length=10000)
    tool_run_id: str = Field(min_length=1, max_length=128)


class DatasetQuality(ContractModel):
    status: QualityStatus
    freshness: FreshnessStatus
    details: list[str] = Field(default_factory=list)


class DataConflict(ContractModel):
    conflict_code: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=2)
    blocking: bool = True


class DataQuality(ContractModel):
    overall_status: QualityStatus
    evidence_coverage: UnitIntervalDecimalValue
    freshness_status: FreshnessStatus
    conflicts_detected: int = Field(ge=0)
    datasets: dict[str, DatasetQuality] = Field(default_factory=dict)
    conflicts: list[DataConflict] = Field(default_factory=list)

    @model_validator(mode="after")
    def conflict_count_matches_details(self) -> "DataQuality":
        if self.conflicts_detected != len(self.conflicts):
            raise ValueError("conflicts_detected must equal the number of conflicts")
        if self.datasets:
            statuses = {item.status for item in self.datasets.values()}
            if QualityStatus.BLOCKED in statuses or QualityStatus.NOT_ASSESSED in statuses:
                expected_status = QualityStatus.BLOCKED
            elif QualityStatus.PARTIAL in statuses:
                expected_status = QualityStatus.PARTIAL
            else:
                expected_status = QualityStatus.COMPLETE
            if self.overall_status != expected_status:
                raise ValueError(
                    "overall_status must agree with all dataset quality statuses"
                )

            freshnesses = {item.freshness for item in self.datasets.values()}
            if FreshnessStatus.STALE in freshnesses:
                expected_freshness = (
                    FreshnessStatus.STALE
                    if freshnesses
                    <= {FreshnessStatus.STALE, FreshnessStatus.UNKNOWN}
                    else FreshnessStatus.MIXED
                )
            elif freshnesses == {FreshnessStatus.FRESH}:
                expected_freshness = FreshnessStatus.FRESH
            elif FreshnessStatus.FRESH in freshnesses:
                expected_freshness = FreshnessStatus.MIXED
            else:
                expected_freshness = FreshnessStatus.UNKNOWN
            if self.freshness_status != expected_freshness:
                raise ValueError(
                    "freshness_status must agree with all dataset freshness statuses"
                )
        return self


class NextAction(ContractModel):
    action: str = Field(min_length=1, max_length=2000)
    target_agent: str = Field(min_length=1, max_length=128)
    mode: Literal["DRY_RUN"] | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class InfoRequest(ContractModel):
    message_type: Literal["INFO_REQUEST"] = "INFO_REQUEST"
    target_agent: Literal["compliance_agent", "document_intelligence_agent"]
    reason: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list)


class ToolErrorDetail(ContractModel):
    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=2000)
    tool_name: str | None = None
    retryable: bool = False


class CreditAnalysisResultV1(ContractModel):
    model_config = ConfigDict(json_schema_extra=_credit_result_schema_metadata)

    schema_version: Literal["1.0"] = "1.0"
    agent: AgentMetadata
    task_id: str | None = Field(min_length=1, max_length=128)
    case_id: str | None = Field(min_length=1, max_length=128)
    as_of_date: date | None
    status: ResultStatus
    recommendation: Recommendation
    relationship_analysis: RelationshipAnalysis | None = None
    facility_analysis: FacilityAnalysis | None = None
    repayment_analysis: RepaymentAnalysis | None = None
    cashflow_analysis: CashflowAnalysis | None = None
    financial_metrics: FinancialMetricsData | None = None
    collateral_analysis: CollateralAnalysis | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list, max_length=5)
    policy_citations: list[PolicyCitation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    data_quality: DataQuality
    next_actions: list[NextAction] = Field(default_factory=list)
    info_requests: list[InfoRequest] = Field(default_factory=list)
    errors: list[ToolErrorDetail] = Field(default_factory=list)
    tool_call_count: int = Field(default=0, ge=0, le=20)

    @model_validator(mode="after")
    def enforce_result_invariants(self) -> "CreditAnalysisResultV1":
        substantive_decisions = {
            Decision.READY_FOR_APPROVAL_REVIEW,
            Decision.PASS_WITH_CONDITIONS,
            Decision.MANUAL_REVIEW,
            Decision.NOT_RECOMMENDED,
        }
        expected_status = {
            Decision.NEEDS_INFO: ResultStatus.NEEDS_INFO,
            Decision.SYSTEM_EXCEPTION: ResultStatus.SYSTEM_EXCEPTION,
        }.get(self.recommendation.decision, ResultStatus.COMPLETED)
        if self.status != expected_status:
            raise ValueError(
                f"status {self.status.value} does not match decision "
                f"{self.recommendation.decision.value}"
            )

        if self.recommendation.decision in {
            Decision.READY_FOR_APPROVAL_REVIEW,
            Decision.PASS_WITH_CONDITIONS,
        }:
            if self.recommendation.recommended_limit is None:
                raise ValueError("positive recommendation requires recommended_limit")
            if self.recommendation.recommended_tenor_months is None:
                raise ValueError("positive recommendation requires recommended_tenor_months")
            if self.recommendation.currency is None:
                raise ValueError("positive recommendation requires currency")

        if self.recommendation.decision in {
            Decision.NEEDS_INFO,
            Decision.MANUAL_REVIEW,
            Decision.NOT_RECOMMENDED,
            Decision.SYSTEM_EXCEPTION,
        } and (
            self.recommendation.recommended_limit is not None
            or self.recommendation.recommended_tenor_months is not None
            or self.recommendation.currency is not None
        ):
            raise ValueError(
                "non-positive decisions cannot carry a recommended amount, tenor, or currency"
            )

        if self.recommendation.decision in substantive_decisions:
            if self.task_id is None or self.case_id is None or self.as_of_date is None:
                raise ValueError(
                    "substantive result requires task_id, case_id, and as_of_date"
                )
            if any(
                item is None
                for item in (
                    self.relationship_analysis,
                    self.facility_analysis,
                    self.repayment_analysis,
                    self.cashflow_analysis,
                    self.financial_metrics,
                )
            ):
                raise ValueError(
                    "substantive result requires every mandatory analysis block"
                )
            if (
                "collateral" in self.data_quality.datasets
                and self.collateral_analysis is None
            ):
                raise ValueError(
                    "substantive collateral case requires collateral_analysis"
                )
            if (
                not self.next_actions
                or self.next_actions[0].target_agent != "validation_agent"
            ):
                raise ValueError(
                    "substantive result must route first to validation_agent"
                )
            required_datasets = {
                "policy",
                "customer_360",
                "credit_facilities",
                "repayment_history",
                "transaction_summary",
                "financial_statements",
                "financial_metrics",
            }
            if not required_datasets.issubset(self.data_quality.datasets):
                raise ValueError(
                    "substantive result requires canonical mandatory dataset quality records"
                )
            if self.tool_call_count < 7:
                raise ValueError("substantive result requires at least seven read tool calls")
            if self.collateral_analysis is not None and self.tool_call_count < 8:
                raise ValueError(
                    "substantive collateral result requires eight read tool calls"
                )
            required_analysis_evidence = {
                "relationship_analysis": (self.relationship_analysis, "ev-customer-360"),
                "facility_analysis": (self.facility_analysis, "ev-credit-facilities"),
                "repayment_analysis": (self.repayment_analysis, "ev-repayment-history"),
                "cashflow_analysis": (self.cashflow_analysis, "ev-transaction-summary"),
            }
            for name, (analysis, evidence_id) in required_analysis_evidence.items():
                if analysis is None or evidence_id not in analysis.evidence_ids:
                    raise ValueError(
                        f"{name} must cite its canonical source evidence"
                    )

        if self.recommendation.decision == Decision.READY_FOR_APPROVAL_REVIEW:
            if self.missing_information or self.conditions:
                raise ValueError("READY result cannot contain missing information or conditions")
            if self.follow_up_questions:
                raise ValueError("READY result cannot contain follow-up questions")
            if (
                self.data_quality.overall_status != QualityStatus.COMPLETE
                or self.data_quality.freshness_status != FreshnessStatus.FRESH
                or self.data_quality.conflicts_detected
                or self.data_quality.conflicts
            ):
                raise ValueError(
                    "READY result requires complete, fresh, conflict-free data quality"
                )
            if self.risk_flags or self.info_requests or self.errors:
                raise ValueError(
                    "READY result cannot contain unresolved risk, info requests, or errors"
                )

        if self.recommendation.decision == Decision.PASS_WITH_CONDITIONS:
            if not self.conditions:
                raise ValueError("PASS_WITH_CONDITIONS requires at least one condition")
            if (
                self.missing_information
                or self.errors
                or self.info_requests
                or self.data_quality.overall_status == QualityStatus.BLOCKED
                or self.data_quality.conflicts_detected
                or self.data_quality.conflicts
            ):
                raise ValueError(
                    "PASS_WITH_CONDITIONS cannot contain missing, blocked, conflict, info-request, or error state"
                )
        if self.recommendation.decision == Decision.NOT_RECOMMENDED:
            if (
                self.missing_information
                or self.info_requests
                or self.data_quality.overall_status != QualityStatus.COMPLETE
                or self.data_quality.freshness_status != FreshnessStatus.FRESH
                or self.data_quality.conflicts_detected
                or self.data_quality.conflicts
                or self.errors
            ):
                raise ValueError(
                    "NOT_RECOMMENDED requires complete, fresh, conflict-free evidence without data gaps"
                )
        if self.recommendation.decision == Decision.NEEDS_INFO and not (
            self.missing_information
            or any(q.blocking_if_unanswered for q in self.follow_up_questions)
        ):
            raise ValueError("NEEDS_INFO requires a concrete missing item or blocking question")
        if self.recommendation.decision == Decision.SYSTEM_EXCEPTION and not self.errors:
            raise ValueError("SYSTEM_EXCEPTION requires an error detail")
        if (
            self.recommendation.decision != Decision.SYSTEM_EXCEPTION
            and self.errors
        ):
            raise ValueError("only SYSTEM_EXCEPTION can carry error details")

        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence_id values must be unique")
        known = set(evidence_ids)
        if self.recommendation.decision in substantive_decisions:
            required_evidence = {
                "ev-input-request",
                "ev-policy",
                "ev-customer-360",
                "ev-credit-facilities",
                "ev-repayment-history",
                "ev-transaction-summary",
                "ev-financial-statements",
                "ev-financial-metrics",
            }
            if "collateral" in self.data_quality.datasets:
                required_evidence.add("ev-collateral")
            missing_evidence = sorted(required_evidence - known)
            if missing_evidence:
                raise ValueError(
                    "substantive result lacks canonical evidence: "
                    + ", ".join(missing_evidence)
                )
            if any(item.as_of_date != self.as_of_date for item in self.evidence):
                raise ValueError(
                    "substantive evidence must be bound to the result as_of_date"
                )
        references: list[str] = list(self.recommendation.evidence_ids)
        for flag in self.risk_flags:
            references.extend(flag.evidence_ids)
        for condition in self.conditions:
            references.extend(condition.evidence_ids)
        for question in self.follow_up_questions:
            references.extend(question.evidence_ids)
        for conflict in self.data_quality.conflicts:
            references.extend(conflict.evidence_ids)
        for message in self.info_requests:
            references.extend(message.evidence_ids)
        for action in self.next_actions:
            references.extend(action.evidence_ids)
        for analysis in (
            self.relationship_analysis,
            self.facility_analysis,
            self.repayment_analysis,
            self.cashflow_analysis,
            self.collateral_analysis,
        ):
            if analysis is not None:
                references.extend(analysis.evidence_ids)
        dangling = sorted(set(references) - known)
        if dangling:
            raise ValueError("dangling evidence references: " + ", ".join(dangling))

        known_claim_ids = {item.claim_id for item in self.evidence}
        dangling_claim_ids = sorted(
            {
                claim_id
                for citation in self.policy_citations
                for claim_id in citation.claim_ids
                if claim_id not in known_claim_ids
            }
        )
        if dangling_claim_ids:
            raise ValueError(
                "dangling policy claim references: " + ", ".join(dangling_claim_ids)
            )

        if self.recommendation.decision in substantive_decisions:
            if not self.recommendation.evidence_ids:
                raise ValueError("substantive recommendation must cite evidence")
            if not self.policy_citations or not all(
                citation.status == PolicyStatus.ACTIVE
                and self.as_of_date is not None
                and citation.effective_from <= self.as_of_date
                and (citation.effective_to is None or self.as_of_date <= citation.effective_to)
                for citation in self.policy_citations
            ):
                raise ValueError(
                    "every substantive policy citation must be active at as_of_date"
                )
            if self.data_quality.evidence_coverage != Decimal("1"):
                raise ValueError(
                    "substantive recommendation requires full canonical evidence coverage"
                )
        return self


class AgentConfig(ContractModel):
    model_config = ConfigDict(frozen=True)

    agent_version: str = "1.0.0"
    max_tool_calls: int = Field(default=20, ge=1, le=20)
    timeout_seconds: float = Field(default=30.0, gt=0, le=30)
    per_tool_timeout_seconds: float = Field(default=10.0, gt=0, le=30)
    max_follow_up_questions: int = Field(default=5, ge=1, le=5)
    fail_on_audit_error: bool = True
    require_audit_sink: bool = False
    audit_timeout_seconds: float = Field(default=1.0, gt=0, le=5)
    allow_placeholder_policy: bool = False


class AuditEvent(ContractModel):
    event_type: str
    run_id: str
    task_id: str | None = None
    occurred_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)
