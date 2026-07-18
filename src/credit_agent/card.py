"""Static registry metadata for the standalone Credit Agent."""

from __future__ import annotations

from typing import Final

from .models import AgentConfig

AGENT_ID: Final = "credit_agent"
AGENT_VERSION: Final = "1.0.0"

ALLOWED_TOOLS: Final[tuple[str, ...]] = (
    "get_customer_360",
    "get_credit_facilities",
    "get_repayment_history",
    "get_transaction_summary",
    "get_financial_statements",
    "calculate_financial_metrics",
    "get_collateral_snapshot",
    "retrieve_credit_policy",
)

TOOL_SCOPES: Final[dict[str, str]] = {
    "get_customer_360": "customer:read",
    "get_credit_facilities": "credit:read",
    "get_repayment_history": "credit:read",
    "get_transaction_summary": "transactions:read",
    "get_financial_statements": "financials:read",
    "calculate_financial_metrics": "financials:read",
    "get_collateral_snapshot": "collateral:read",
    "retrieve_credit_policy": "policy:read",
}

_AGENT_CARD: Final[dict[str, object]] = {
    "agent_id": AGENT_ID,
    "name": "SME Credit Renewal Agent",
    "version": AGENT_VERSION,
    "status": "ONLINE",
    "description": "Analyzes SME credit renewal and limit-review tasks",
    "capabilities": [
        "customer_relationship_analysis",
        "credit_facility_analysis",
        "repayment_behavior_analysis",
        "transaction_cashflow_analysis",
        "financial_statement_analysis",
        "collateral_coverage_analysis",
        "credit_policy_matching",
        "credit_recommendation_drafting",
    ],
    "supported_tasks": ["CREDIT_RENEWAL_REVIEW", "CREDIT_LIMIT_REVIEW"],
    "allowed_tools": list(ALLOWED_TOOLS),
    "forbidden_actions": [
        "APPROVE_CREDIT",
        "COMMIT_CREDIT_CHANGE",
        "MODIFY_CUSTOMER_DATA",
        "EXECUTE_PAYMENT",
    ],
    "input_schema": "CreditTaskInputV1",
    "output_schema": "CreditAnalysisResultV1",
    "risk_tier": "HIGH",
    "human_approval_required": True,
    "max_tool_calls": 20,
    "max_follow_up_questions": 5,
    "timeout_seconds": 30,
}


def get_agent_card(
    config: AgentConfig | None = None, *, online: bool = True
) -> dict[str, object]:
    """Return runtime-aligned registry metadata as a defensive deep copy."""

    import copy

    card = copy.deepcopy(_AGENT_CARD)
    card["status"] = "ONLINE" if online else "OFFLINE"
    if config is not None:
        card["version"] = config.agent_version
        card["max_tool_calls"] = config.max_tool_calls
        card["max_follow_up_questions"] = config.max_follow_up_questions
        card["timeout_seconds"] = config.timeout_seconds
        card["audit_required"] = config.require_audit_sink
    return card
