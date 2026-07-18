from __future__ import annotations

import asyncio
from typing import Any, Callable

from credit_agent.agent import CreditAgent
from credit_agent.models import (
    AgentConfig,
    CollateralPolicyMode,
    Decision,
    Permissions,
    PolicyStatus,
    ResultStatus,
)


def test_missing_read_scope_stops_before_any_tool(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.task = case.task.model_copy(
        update={
            "permissions": Permissions(
                allowed_scopes=case.task.permissions.allowed_scopes - {"policy:read"}
            )
        }
    )

    result = asyncio.run(CreditAgent(tools=case.tools).run(case.task))

    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.recommendation.decision == Decision.SYSTEM_EXCEPTION
    assert result.errors[0].code == "MISSING_READ_SCOPE"
    assert result.tool_call_count == 0
    assert case.tools.calls == []


def test_inactive_policy_stops_before_customer_data_reads(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["retrieve_credit_policy"]
    assert envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = envelope.model_copy(
        update={
            "data": envelope.data.model_copy(update={"status": PolicyStatus.EXPIRED})
        }
    )

    result = asyncio.run(CreditAgent(tools=case.tools).run(case.task))

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert result.tool_call_count == 1
    assert case.tools.calls == ["retrieve_credit_policy"]
    assert result.recommendation.recommended_limit is None


def test_unsecured_case_skips_collateral_tool_and_scope(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    request = case.task.credit_request.model_copy(update={"collateral_required": False})
    scopes = case.task.permissions.allowed_scopes - {"collateral:read"}
    case.task = case.task.model_copy(
        update={
            "credit_request": request,
            "permissions": Permissions(allowed_scopes=scopes),
        }
    )
    policy_envelope = case.tools.outputs["retrieve_credit_policy"]
    assert policy_envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = policy_envelope.model_copy(
        update={
            "data": policy_envelope.data.model_copy(
                update={"collateral_mode": CollateralPolicyMode.OPTIONAL}
            )
        }
    )
    case.tools.fail_if_called.add("get_collateral_snapshot")

    result = asyncio.run(CreditAgent(tools=case.tools).run(case.task))

    assert result.recommendation.decision == Decision.READY_FOR_APPROVAL_REVIEW
    assert result.tool_call_count == 7
    assert "get_collateral_snapshot" not in case.tools.calls
    assert result.collateral_analysis is None


def test_configured_tool_budget_is_a_control_exception(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    agent = CreditAgent(tools=case.tools, config=AgentConfig(max_tool_calls=1))

    result = asyncio.run(agent.run(case.task))

    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.recommendation.decision == Decision.SYSTEM_EXCEPTION
    assert result.errors[0].code == "TOOL_BUDGET_EXCEEDED"
    assert result.tool_call_count == 1
