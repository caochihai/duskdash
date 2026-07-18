"""Authorization-first deterministic context routing."""

from __future__ import annotations

from app.compat import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContextStatus(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    MISSING = "MISSING"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class RouteType(StrEnum):
    REFUSE = "REFUSE"
    DIRECT = "DIRECT"
    SINGLE_AGENT = "SINGLE_AGENT"
    ORCHESTRATED = "ORCHESTRATED"


_REPAYMENT_TERMS = (
    "dti",
    "dscr",
    "repayment",
    "affordability",
    "khả năng trả nợ",
    "năng lực trả nợ",
    "nghĩa vụ nợ",
)
_LOAN_ANALYSIS_TERMS = (
    "đánh giá khoản vay",
    "phân tích khoản vay",
    "thẩm định khoản vay",
    "loan assessment",
    "loan analysis",
)
_DEFINITION_TERMS = ("là gì", "nghĩa là gì", "what is", "define", "giải thích khái niệm")
_DOCUMENT_TERMS = (
    "document",
    "hồ sơ",
    "ocr",
    "mâu thuẫn",
    "xung đột",
    "dấu đỏ",
    "con dấu",
    "chữ ký",
)
_COMPLIANCE_TERMS = (
    "chính sách",
    "policy",
    "pháp lý",
    "pháp luật",
    "compliance",
    "quy định",
)
_CREDIT_TERMS = (
    "credit",
    "loan",
    "khoản vay",
    "tín dụng",
    "thu nhập",
    "dòng tiền",
    "giao dịch",
    "tài chính",
    "nghĩa vụ",
    "income",
    "cash flow",
    "transaction",
    "financial",
)
_EXPLICIT_OUT_OF_SCOPE_TERMS = (
    "dự báo thời tiết",
    "weather forecast",
    "kết quả bóng đá",
    "football score",
    "công thức nấu ăn",
    "recipe",
    "viết thơ",
    "write a poem",
    "kể chuyện cười",
    "tell me a joke",
)


class RoutingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    employee_id: UUID
    message: str
    active_customer_id: UUID | None = None
    active_loan_application_id: UUID | None = None
    attachment_ids: tuple[UUID, ...] = ()
    accessible_customer_ids: frozenset[UUID] = frozenset()
    accessible_loan_ids: frozenset[UUID] = frozenset()


class RoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: UUID | None
    loan_application_id: UUID | None
    intent: str
    normalized_question: str
    context_status: ContextStatus
    complexity_level: int = Field(ge=1, le=4)
    route_type: RouteType
    missing_context: tuple[str, ...]
    required_agents: tuple[str, ...]
    attachment_ids: tuple[UUID, ...] = ()


class ContextRouter:
    async def route(self, request: RoutingRequest) -> RoutingDecision:
        # Authorization deliberately precedes any semantic classification.
        if request.active_customer_id and request.active_customer_id not in request.accessible_customer_ids:
            raise PermissionError("current employee cannot access the selected customer")
        if (
            request.active_loan_application_id
            and request.active_loan_application_id not in request.accessible_loan_ids
        ):
            raise PermissionError("current employee cannot access the selected loan application")

        normalized = " ".join(request.message.split())
        lowered = normalized.casefold()
        if normalized and _contains_any(lowered, _EXPLICIT_OUT_OF_SCOPE_TERMS):
            return _refusal(request, normalized)

        domain_agents = _domain_agents(lowered)
        is_definition = (
            _contains_any(lowered, _DEFINITION_TERMS)
            and bool(domain_agents or _contains_any(lowered, _REPAYMENT_TERMS))
        )
        requires_loan = (
            _contains_any(lowered, _LOAN_ANALYSIS_TERMS)
            or (
                _contains_any(lowered, _REPAYMENT_TERMS)
                and not is_definition
            )
        )

        # An unknown prompt is not implicitly trusted as a general-purpose chat
        # request.  Refuse it before asking for customer context so prompts such
        # as "Write Python code" cannot fall through to the DIRECT route.
        if normalized and not (domain_agents or requires_loan or is_definition):
            return _refusal(request, normalized)

        missing: list[str] = []
        if request.active_customer_id is None and not is_definition:
            missing.append("customer_id")
        if not normalized:
            missing.append("question")
        if requires_loan and request.active_loan_application_id is None:
            missing.append("loan_application_id")
        if missing:
            return RoutingDecision(
                customer_id=request.active_customer_id,
                loan_application_id=request.active_loan_application_id,
                intent="MISSING_CONTEXT",
                normalized_question=normalized,
                context_status=ContextStatus.MISSING,
                complexity_level=1,
                route_type=RouteType.DIRECT,
                missing_context=tuple(missing),
                required_agents=(),
                attachment_ids=request.attachment_ids,
            )

        if is_definition:
            return RoutingDecision(
                customer_id=request.active_customer_id,
                loan_application_id=request.active_loan_application_id,
                intent="DIRECT_QUERY",
                normalized_question=normalized,
                context_status=ContextStatus.SUFFICIENT,
                complexity_level=2,
                route_type=RouteType.DIRECT,
                missing_context=(),
                required_agents=(),
                attachment_ids=request.attachment_ids,
            )

        if requires_loan or len(domain_agents) >= 2:
            return RoutingDecision(
                customer_id=request.active_customer_id,
                loan_application_id=request.active_loan_application_id,
                intent=(
                    "ASSESS_REPAYMENT_CAPACITY"
                    if requires_loan
                    else "CROSS_DOMAIN_ANALYSIS"
                ),
                normalized_question=normalized,
                context_status=ContextStatus.SUFFICIENT,
                complexity_level=4,
                route_type=RouteType.ORCHESTRATED,
                missing_context=(),
                required_agents=(
                    ("DOCUMENT", "CREDIT", "LEGAL_COMPLIANCE")
                    if requires_loan
                    else domain_agents
                ),
                attachment_ids=request.attachment_ids,
            )
        agents: tuple[str, ...]
        if domain_agents == ("LEGAL_COMPLIANCE",):
            agents = ("LEGAL_COMPLIANCE",)
            route_type = RouteType.SINGLE_AGENT
            complexity = 3
            intent = "CHECK_POLICY_COMPLIANCE"
        elif domain_agents == ("DOCUMENT",):
            agents = ("DOCUMENT",)
            route_type = RouteType.SINGLE_AGENT
            complexity = 3
            intent = "REVIEW_DOCUMENTS"
        elif domain_agents == ("CREDIT",):
            agents = ("CREDIT",)
            route_type = RouteType.SINGLE_AGENT
            complexity = 3
            intent = "REVIEW_FINANCIAL_INFORMATION"
        else:
            # Empty questions are handled as missing context above.  This is a
            # defensive fallback for any future classifier extension.
            return _refusal(request, normalized)
        return RoutingDecision(
            customer_id=request.active_customer_id,
            loan_application_id=request.active_loan_application_id,
            intent=intent,
            normalized_question=normalized,
            context_status=ContextStatus.SUFFICIENT,
            complexity_level=complexity,
            route_type=route_type,
            missing_context=(),
            required_agents=agents,
            attachment_ids=request.attachment_ids,
        )


def _contains_any(message: str, terms: tuple[str, ...]) -> bool:
    return any(term in message for term in terms)


def _domain_agents(message: str) -> tuple[str, ...]:
    """Return matched expert domains in canonical DAG order."""

    return tuple(
        agent
        for agent, terms in (
            ("DOCUMENT", _DOCUMENT_TERMS),
            ("CREDIT", _CREDIT_TERMS),
            ("LEGAL_COMPLIANCE", _COMPLIANCE_TERMS),
        )
        if _contains_any(message, terms)
    )


def _refusal(request: RoutingRequest, normalized: str) -> RoutingDecision:
    return RoutingDecision(
        customer_id=request.active_customer_id,
        loan_application_id=request.active_loan_application_id,
        intent="OUT_OF_SCOPE",
        normalized_question=normalized,
        context_status=ContextStatus.OUT_OF_SCOPE,
        # Refusal is a simple deterministic response, not a fifth complexity
        # level in the canonical 1-4 contract.
        complexity_level=2,
        route_type=RouteType.REFUSE,
        missing_context=(),
        required_agents=(),
        attachment_ids=request.attachment_ids,
    )
