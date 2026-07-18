from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError as PydanticValidationError

from credit_agent.agent import CreditAgent
from credit_agent.api import create_app
from credit_agent.audit import InMemoryAuditSink, NullAuditSink
from credit_agent.demo_tools import DemoCreditTools
from credit_agent.models import (
    AgentConfig,
    CoveragePeriod,
    CreditAnalysisResultV1,
    Decision,
    Permissions,
    QualityStatus,
    ResultStatus,
    CreditTaskInputV1,
)


def _run(case: Any, task: Any | None = None) -> CreditAnalysisResultV1:
    return asyncio.run(CreditAgent(tools=case.tools).run(task or case.task))


def test_checked_in_demo_is_a_labeled_happy_path() -> None:
    payload_path = Path(__file__).resolve().parents[1] / "examples" / "credit_task.json"
    task = CreditTaskInputV1.model_validate(
        json.loads(payload_path.read_text(encoding="utf-8"))
    )

    result = asyncio.run(
        CreditAgent(
            tools=DemoCreditTools(),
            config=AgentConfig(allow_placeholder_policy=True),
        ).run(task)
    )

    assert result.recommendation.decision == Decision.READY_FOR_APPROVAL_REVIEW
    assert "placeholder" in result.recommendation.summary.lower()


def test_model_copy_cannot_bypass_input_validation(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    invalid_request = case.task.credit_request.model_copy(
        update={"requested_limit": Decimal("0")}
    )
    bypass_attempt = case.task.model_copy(
        update={"credit_request": invalid_request}
    )

    result = _run(case, bypass_attempt)

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert result.tool_call_count == 0
    assert case.tools.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [("task_id", "   "), ("case_id", "x" * 129)],
)
def test_invalid_identity_still_returns_the_unified_needs_info_contract(
    credit_case_factory: Callable[[], Any], field: str, value: str
) -> None:
    case = credit_case_factory()
    payload = case.task.model_dump(mode="json")
    payload[field] = value

    result = _run(case, payload)

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert result.tool_call_count == 0
    assert case.tools.calls == []


def test_requested_product_facility_must_reconcile_to_aggregate_and_currency(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["get_credit_facilities"]
    assert envelope.data is not None
    mismatched_record = envelope.data.facilities[0].model_copy(
        update={
            "approved_limit": Decimal("100"),
            "outstanding": Decimal("75"),
            "utilization_ratio": Decimal("0.75"),
            "currency": "USD",
        }
    )
    case.tools.update_data("get_credit_facilities", facilities=[mismatched_record])

    result = _run(case)

    assert result.recommendation.decision == Decision.MANUAL_REVIEW
    assert "REQUESTED_PRODUCT_FACILITY_CONFLICT" in {
        conflict.conflict_code for conflict in result.data_quality.conflicts
    }


def test_collateral_coverage_ratio_must_reconcile_to_eligible_value_and_basis(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data(
        "get_collateral_snapshot",
        appraised_value=Decimal("0"),
        eligible_value=Decimal("0"),
        coverage_ratio=Decimal("1.50"),
        coverage_denominator=Decimal("1000000"),
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.MANUAL_REVIEW
    assert "COLLATERAL_COVERAGE_RATIO_CONFLICT" in {
        conflict.conflict_code for conflict in result.data_quality.conflicts
    }


def test_stated_coverage_months_cannot_hide_stale_windows(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    stale_window = CoveragePeriod(
        start_date=date(2024, 7, 1), end_date=date(2025, 6, 30)
    )
    case.tools.update_data(
        "get_repayment_history",
        lookback_months=12,
        coverage_period=stale_window,
    )
    case.tools.update_data(
        "get_transaction_summary",
        coverage_months=12,
        coverage_period=stale_window,
    )

    result = _run(case)

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert result.data_quality.datasets["repayment_history"].status == QualityStatus.BLOCKED
    assert result.data_quality.datasets["transaction_summary"].status == QualityStatus.BLOCKED
    assert result.recommendation.recommended_limit is None


def test_repeated_short_late_payments_cannot_silently_pass(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data(
        "get_repayment_history",
        late_payment_count=100,
        max_days_past_due=1,
        current_days_past_due=0,
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert "REPEATED_LATE_PAYMENTS" in {
        flag.code.value for flag in result.risk_flags
    }


def test_transaction_cash_stress_cannot_silently_pass(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data(
        "get_transaction_summary",
        average_monthly_inflow=Decimal("0"),
        average_monthly_outflow=Decimal("999999999999"),
        inflow_volatility=Decimal("999"),
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert {
        "HIGH_INFLOW_VOLATILITY",
        "LOW_TRANSACTION_CASH_COVERAGE",
    } <= {flag.code.value for flag in result.risk_flags}


def test_missing_mandatory_metric_value_blocks_positive_recommendation(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["calculate_financial_metrics"]
    assert envelope.data is not None
    metrics = dict(envelope.data.metrics)
    metrics["dscr"] = metrics["dscr"].model_copy(update={"current": None})
    case.tools.outputs["calculate_financial_metrics"] = envelope.model_copy(
        update={"data": envelope.data.model_copy(update={"metrics": metrics})}
    )

    result = _run(case)

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert result.data_quality.datasets["financial_metrics"].status == QualityStatus.BLOCKED
    assert any("dscr" in item for item in result.missing_information)


def test_tool_response_context_binding_mismatch_fails_closed(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["get_customer_360"]
    case.tools.outputs["get_customer_360"] = envelope.model_copy(
        update={"case_id": "another-case"}
    )

    result = _run(case)

    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.recommendation.decision == Decision.SYSTEM_EXCEPTION
    assert result.errors[0].code == "MANDATORY_TOOL_FAILED"
    assert result.errors[0].tool_name == "get_customer_360"
    assert result.recommendation.recommended_limit is None


def test_policy_must_match_product_before_customer_reads(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["retrieve_credit_policy"]
    assert envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = envelope.model_copy(
        update={
            "data": envelope.data.model_copy(
                update={"applicable_product_codes": {"OTHER-PRODUCT"}}
            )
        }
    )

    result = _run(case)

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert result.tool_call_count == 1
    assert case.tools.calls == ["retrieve_credit_policy"]


@pytest.mark.parametrize(
    ("changes", "expected_tool"),
    [
        ({"applicable_segments": set()}, "retrieve_credit_policy"),
        ({"document_id": "   "}, "retrieve_credit_policy"),
        ({"version": ""}, "retrieve_credit_policy"),
    ],
)
def test_invalid_policy_identity_or_applicability_fails_contract_validation(
    credit_case_factory: Callable[[], Any],
    changes: dict[str, Any],
    expected_tool: str,
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["retrieve_credit_policy"]
    assert envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = envelope.model_copy(
        update={"data": envelope.data.model_copy(update=changes)}
    )

    result = _run(case)

    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.errors[0].code == "MANDATORY_TOOL_FAILED"
    assert result.errors[0].tool_name == expected_tool
    assert case.tools.calls == ["retrieve_credit_policy"]


def test_placeholder_policy_requires_explicit_demo_configuration(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["retrieve_credit_policy"]
    assert envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = envelope.model_copy(
        update={"data": envelope.data.model_copy(update={"placeholder_data": True})}
    )

    result = _run(case)

    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.errors[0].code == "PLACEHOLDER_POLICY_FORBIDDEN"
    assert case.tools.calls == ["retrieve_credit_policy"]


@pytest.mark.parametrize(
    "threshold_name",
    ["outstanding_conflict_tolerance_ratio", "low_limit_utilization_threshold"],
)
def test_policy_ratio_thresholds_cannot_exceed_one(
    credit_case_factory: Callable[[], Any], threshold_name: str
) -> None:
    case = credit_case_factory()
    case.tools.update_policy_thresholds(**{threshold_name: Decimal("2")})

    result = _run(case)

    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.errors[0].tool_name == "retrieve_credit_policy"
    assert case.tools.calls == ["retrieve_credit_policy"]


def test_policy_must_match_authoritative_customer_segment(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["retrieve_credit_policy"]
    assert envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = envelope.model_copy(
        update={
            "data": envelope.data.model_copy(
                update={"applicable_segments": {"CORPORATE"}}
            )
        }
    )

    result = _run(case)

    assert result.status == ResultStatus.NEEDS_INFO
    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert "calculate_financial_metrics" not in case.tools.calls
    assert result.tool_call_count == 2
    assert case.tools.calls == ["retrieve_credit_policy", "get_customer_360"]


def test_policy_clause_claim_ids_are_resolved_without_hard_coded_coupling(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["retrieve_credit_policy"]
    assert envelope.data is not None
    clauses = [
        clause.model_copy(update={"claim_ids": {"policy-claim-custom-001"}})
        for clause in envelope.data.clauses
    ]
    case.tools.outputs["retrieve_credit_policy"] = envelope.model_copy(
        update={"data": envelope.data.model_copy(update={"clauses": clauses})}
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.READY_FOR_APPROVAL_REVIEW
    known_claims = {item.claim_id for item in result.evidence}
    cited_claims = {
        claim_id
        for citation in result.policy_citations
        for claim_id in citation.claim_ids
    }
    assert cited_claims == {"policy-claim-custom-001"}
    assert cited_claims <= known_claims


def test_transaction_currency_conflict_cannot_silently_pass(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data("get_transaction_summary", currency="USD")

    result = _run(case)

    assert result.recommendation.decision == Decision.MANUAL_REVIEW
    assert "CURRENCY_CONFLICT" in {
        item.conflict_code for item in result.data_quality.conflicts
    }
    assert result.recommendation.recommended_limit is None


def test_post_cutoff_rating_cannot_silently_pass(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data("get_customer_360", rating_as_of=date(2026, 7, 1))

    result = _run(case)

    assert result.recommendation.decision == Decision.MANUAL_REVIEW
    assert "POST_CUTOFF_CUSTOMER_RATING" in {
        item.conflict_code for item in result.data_quality.conflicts
    }


def test_stale_internal_rating_uses_policy_freshness_threshold(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data("get_customer_360", rating_as_of=date(2024, 1, 1))

    result = _run(case)

    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert "STALE_INTERNAL_RATING" in {
        flag.code.value for flag in result.risk_flags
    }
    assert result.data_quality.datasets["customer_360"].freshness.value == "STALE"


def test_policy_classifies_ineligible_customer_categories(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data(
        "get_customer_360",
        internal_rating="DEFAULT",
        relationship_status="BLOCKED",
    )
    policy_envelope = case.tools.outputs["retrieve_credit_policy"]
    assert policy_envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = policy_envelope.model_copy(
        update={
            "data": policy_envelope.data.model_copy(
                update={
                    "not_recommended_flag_codes": {
                        "INTERNAL_RATING_OUTSIDE_POLICY",
                        "RELATIONSHIP_STATUS_OUTSIDE_POLICY",
                    }
                }
            )
        }
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.NOT_RECOMMENDED
    assert {
        "INTERNAL_RATING_OUTSIDE_POLICY",
        "RELATIONSHIP_STATUS_OUTSIDE_POLICY",
    } <= {flag.code.value for flag in result.risk_flags}


def test_over_limit_exposure_requires_explicit_policy_treatment(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data("get_customer_360", total_outstanding=Decimal("2000000"))
    case.tools.update_data(
        "get_credit_facilities",
        outstanding=Decimal("2000000"),
        utilization_ratio=Decimal("2"),
        facilities=[
            case.tools.outputs["get_credit_facilities"].data.facilities[0].model_copy(
                update={
                    "outstanding": Decimal("2000000"),
                    "utilization_ratio": Decimal("2"),
                }
            )
        ],
    )
    statements = case.tools.outputs["get_financial_statements"]
    assert statements.data is not None and statements.data.current is not None
    case.tools.update_data(
        "get_financial_statements",
        current=statements.data.current.model_copy(
            update={"total_debt": Decimal("2000000")}
        ),
    )
    policy_envelope = case.tools.outputs["retrieve_credit_policy"]
    assert policy_envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = policy_envelope.model_copy(
        update={
            "data": policy_envelope.data.model_copy(
                update={"not_recommended_flag_codes": {"OVER_LIMIT_EXPOSURE"}}
            )
        }
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.NOT_RECOMMENDED
    assert "OVER_LIMIT_EXPOSURE" in {flag.code.value for flag in result.risk_flags}
    assert result.recommendation.recommended_limit is None


def test_facility_records_must_match_the_requested_product(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["get_credit_facilities"]
    assert envelope.data is not None
    unrelated = [
        facility.model_copy(update={"product_code": "UNRELATED-PRODUCT"})
        for facility in envelope.data.facilities
    ]
    case.tools.update_data("get_credit_facilities", facilities=unrelated)

    result = _run(case)

    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert "facility record matching the requested product" in result.missing_information
    assert result.data_quality.datasets["credit_facilities"].status == QualityStatus.BLOCKED


def test_facility_utilization_is_reconciled_to_limit_and_outstanding(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["get_credit_facilities"]
    assert envelope.data is not None
    inconsistent_records = [
        facility.model_copy(update={"utilization_ratio": Decimal("0.10")})
        for facility in envelope.data.facilities
    ]
    case.tools.update_data(
        "get_credit_facilities",
        utilization_ratio=Decimal("0.10"),
        facilities=inconsistent_records,
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.MANUAL_REVIEW
    assert "FACILITY_UTILIZATION_CONFLICT" in {
        conflict.conflict_code for conflict in result.data_quality.conflicts
    }


def test_collateral_status_requires_policy_classification(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    case.tools.update_data("get_collateral_snapshot", valuation_status="INVALID")
    policy_envelope = case.tools.outputs["retrieve_credit_policy"]
    assert policy_envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = policy_envelope.model_copy(
        update={
            "data": policy_envelope.data.model_copy(
                update={
                    "not_recommended_flag_codes": {
                        "COLLATERAL_STATUS_OUTSIDE_POLICY"
                    }
                }
            )
        }
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.NOT_RECOMMENDED
    assert "COLLATERAL_STATUS_OUTSIDE_POLICY" in {
        flag.code.value for flag in result.risk_flags
    }


def test_metric_provenance_is_mandatory(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["calculate_financial_metrics"]
    assert envelope.data is not None
    metrics = dict(envelope.data.metrics)
    metrics["dscr"] = metrics["dscr"].model_copy(
        update={"formula": "", "unit": "", "input_references": []}
    )
    case.tools.outputs["calculate_financial_metrics"] = envelope.model_copy(
        update={"data": envelope.data.model_copy(update={"metrics": metrics})}
    )

    result = _run(case)

    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.errors[0].code == "MANDATORY_TOOL_FAILED"
    assert result.errors[0].tool_name == "calculate_financial_metrics"


def test_audited_statement_requirement_is_policy_driven_and_disclosed(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    envelope = case.tools.outputs["get_financial_statements"]
    assert envelope.data is not None
    assert envelope.data.current is not None and envelope.data.prior is not None
    case.tools.update_data(
        "get_financial_statements",
        current=envelope.data.current.model_copy(update={"audited": False}),
        prior=envelope.data.prior.model_copy(update={"audited": False}),
    )

    result = _run(case)

    assert result.recommendation.decision == Decision.NEEDS_INFO
    assert "audited current and prior financial statements" in result.missing_information
    financial_evidence = next(
        item for item in result.evidence if item.evidence_id == "ev-financial-statements"
    )
    assert "unaudited" in financial_evidence.fact


def test_policy_classified_metric_breach_can_be_not_recommended(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    metrics_envelope = case.tools.outputs["calculate_financial_metrics"]
    assert metrics_envelope.data is not None
    metrics = dict(metrics_envelope.data.metrics)
    metrics["dscr"] = metrics["dscr"].model_copy(
        update={"current": Decimal("0.80")}
    )
    case.tools.outputs["calculate_financial_metrics"] = metrics_envelope.model_copy(
        update={"data": metrics_envelope.data.model_copy(update={"metrics": metrics})}
    )

    policy_envelope = case.tools.outputs["retrieve_credit_policy"]
    assert policy_envelope.data is not None
    case.tools.outputs["retrieve_credit_policy"] = policy_envelope.model_copy(
        update={
            "data": policy_envelope.data.model_copy(
                update={"not_recommended_metric_names": {"dscr"}}
            )
        }
    )

    result = _run(case)

    assert result.status == ResultStatus.COMPLETED
    assert result.recommendation.decision == Decision.NOT_RECOMMENDED
    assert result.recommendation.recommended_limit is None
    assert result.recommendation.recommended_tenor_months is None


def test_decimal_wire_values_are_exact_strings_and_schema_agrees(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    result = _run(case)

    payload = result.model_dump(mode="json")
    assert payload["recommendation"]["recommended_limit"] == "1000000"
    assert isinstance(payload["recommendation"]["recommended_limit"], str)
    assert json.loads(result.model_dump_json())["recommendation"][
        "recommended_limit"
    ] == "1000000"

    schema = CreditAnalysisResultV1.model_json_schema(mode="serialization")
    amount_schema = schema["$defs"]["Recommendation"]["properties"][
        "recommended_limit"
    ]
    assert {item.get("type") for item in amount_schema["anyOf"]} == {
        "string",
        "null",
    }
    assert any(item.get("format") == "decimal" for item in amount_schema["anyOf"])


class _SlowAuditSink:
    async def emit(self, event: Any) -> None:
        del event
        await asyncio.sleep(0.20)


class _DurableMemoryAuditSink(InMemoryAuditSink):
    """Test double for the production sink capability contract."""

    durable = True


def test_production_audit_configuration_is_fail_closed(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    with pytest.raises(ValueError, match="durable=True"):
        CreditAgent(
            tools=case.tools,
            audit_sink=InMemoryAuditSink(),
            config=AgentConfig(require_audit_sink=True),
        )

    with pytest.raises(ValueError, match="fail_on_audit_error=True"):
        CreditAgent(
            tools=case.tools,
            audit_sink=_DurableMemoryAuditSink(),
            config=AgentConfig(
                require_audit_sink=True,
                fail_on_audit_error=False,
            ),
        )

    placeholder_agent = CreditAgent(
        tools=case.tools,
        audit_sink=_DurableMemoryAuditSink(),
        config=AgentConfig(
            require_audit_sink=True,
            allow_placeholder_policy=True,
        ),
    )
    with pytest.raises(ValueError, match="allow_placeholder_policy=True"):
        create_app(
            placeholder_agent,
            scope_resolver=lambda request: {"policy:read"},
            task_authorizer=lambda request, task: True,
        )


def test_agent_config_is_immutable_after_startup() -> None:
    config = AgentConfig(require_audit_sink=True)

    with pytest.raises(PydanticValidationError, match="frozen"):
        config.fail_on_audit_error = False


def test_agent_control_dependencies_are_immutable_after_startup(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    agent = CreditAgent(
        tools=case.tools,
        audit_sink=_DurableMemoryAuditSink(),
        config=AgentConfig(require_audit_sink=True),
    )

    with pytest.raises(AttributeError, match="immutable"):
        agent.audit_sink = NullAuditSink()
    with pytest.raises(AttributeError, match="immutable"):
        agent.config = AgentConfig()
    with pytest.raises(AttributeError, match="immutable"):
        agent.tools = case.tools


def test_audit_sink_cannot_hang_the_agent_deadline(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    agent = CreditAgent(
        tools=case.tools,
        audit_sink=_SlowAuditSink(),
        config=AgentConfig(
            timeout_seconds=0.10,
            audit_timeout_seconds=0.02,
            fail_on_audit_error=True,
        ),
    )

    started = time.perf_counter()
    result = asyncio.run(agent.run(case.task))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.15
    assert result.status == ResultStatus.SYSTEM_EXCEPTION
    assert result.errors[0].code == "AGENT_DEADLINE_EXCEEDED"
    assert case.tools.calls == []


def test_api_is_unconfigured_by_default_and_demo_is_explicit(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()

    async def exercise() -> None:
        unconfigured = create_app()
        transport = httpx.ASGITransport(app=unconfigured)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            health = await client.get("/health")
            response = await client.post(
                "/v1/credit-analysis", json=case.task.model_dump(mode="json")
            )
        assert health.status_code == 503
        assert health.json()["runtime_mode"] == "unconfigured"
        assert health.headers["X-Credit-Agent-Mode"] == "unconfigured"
        assert response.status_code == 503

        demo = create_app(demo_mode=True)
        transport = httpx.ASGITransport(app=demo)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["runtime_mode"] == "demo"
        assert health.headers["X-Credit-Agent-Mode"] == "demo"

    asyncio.run(exercise())


def test_openapi_documents_fail_closed_and_metadata_responses() -> None:
    schema = create_app().openapi()

    assert schema["x-authentication-boundary"]["provided_by"] == "host_gateway"
    result_schema = schema["components"]["schemas"]["CreditAnalysisResultV1"]
    assert len(result_schema["allOf"]) == 5
    assert result_schema["x-credit-agent-runtime-invariants"]

    analysis_responses = schema["paths"]["/v1/credit-analysis"]["post"][
        "responses"
    ]
    assert {"200", "403", "422", "503"} <= set(analysis_responses)
    assert analysis_responses["403"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/ErrorResponse")

    health_responses = schema["paths"]["/health"]["get"]["responses"]
    assert {"200", "503"} <= set(health_responses)
    assert health_responses["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/HealthResponse")

    card_schema = schema["paths"]["/agent-card"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert card_schema["$ref"].endswith("/AgentCardResponse")


def test_api_does_not_echo_invalid_inputs_and_ignores_self_granted_scopes(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()

    async def exercise() -> None:
        demo = create_app(demo_mode=True)
        invalid = case.task.model_dump(mode="json")
        invalid["customer_id"] = "secret-customer-value"
        invalid["credit_request"]["requested_limit"] = "0"
        transport = httpx.ASGITransport(app=demo)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post("/v1/credit-analysis", json=invalid)
        assert response.status_code == 422
        assert "secret-customer-value" not in response.text
        assert '"input"' not in response.text

        sink = _DurableMemoryAuditSink()
        production_agent = CreditAgent(
            tools=case.tools,
            audit_sink=sink,
            config=AgentConfig(require_audit_sink=True),
        )

        async def trusted_scopes(request: Any) -> frozenset[str]:
            del request
            return case.task.permissions.allowed_scopes - {"policy:read"}

        production = create_app(
            production_agent,
            scope_resolver=trusted_scopes,
            task_authorizer=lambda request, task: True,
        )
        transport = httpx.ASGITransport(app=production)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/credit-analysis", json=case.task.model_dump(mode="json")
            )
        assert response.status_code == 200
        result = response.json()
        assert result["recommendation"]["decision"] == "SYSTEM_EXCEPTION"
        assert result["errors"][0]["code"] == "MISSING_READ_SCOPE"
        assert case.tools.calls == []

    asyncio.run(exercise())


def test_api_enforces_record_level_task_authorization(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    agent = CreditAgent(
        tools=case.tools,
        audit_sink=_DurableMemoryAuditSink(),
        config=AgentConfig(require_audit_sink=True),
    )

    async def exercise() -> None:
        application = create_app(
            agent,
            scope_resolver=lambda request: case.task.permissions.allowed_scopes,
            task_authorizer=lambda request, task: False,
        )
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/credit-analysis", json=case.task.model_dump(mode="json")
            )
        assert response.status_code == 403
        assert response.json() == {
            "detail": "Task is not authorized for this principal"
        }
        assert case.tools.calls == []

    asyncio.run(exercise())


def test_api_rejects_empty_trusted_scopes_before_any_tool_call(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    agent = CreditAgent(
        tools=case.tools,
        audit_sink=_DurableMemoryAuditSink(),
        config=AgentConfig(require_audit_sink=True),
    )

    async def exercise() -> None:
        application = create_app(
            agent,
            scope_resolver=lambda request: set(),
            task_authorizer=lambda request, task: True,
        )
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/credit-analysis", json=case.task.model_dump(mode="json")
            )
        assert response.status_code == 403
        assert response.json() == {"detail": "No authorized read scopes"}
        assert case.tools.calls == []

    asyncio.run(exercise())


def test_api_fails_closed_when_authorization_dependency_times_out_or_errors(
    credit_case_factory: Callable[[], Any],
) -> None:
    case = credit_case_factory()
    agent = CreditAgent(
        tools=case.tools,
        audit_sink=_DurableMemoryAuditSink(),
        config=AgentConfig(require_audit_sink=True),
    )

    async def slow_scopes(request: Any) -> frozenset[str]:
        del request
        await asyncio.sleep(0.05)
        return case.task.permissions.allowed_scopes

    def broken_authorizer(request: Any, task: Any) -> bool:
        del request, task
        raise RuntimeError("identity-provider-detail-must-not-leak")

    async def exercise() -> None:
        timeout_app = create_app(
            agent,
            scope_resolver=slow_scopes,
            task_authorizer=lambda request, task: True,
            authorization_timeout_seconds=0.01,
        )
        transport = httpx.ASGITransport(app=timeout_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            timeout_response = await client.post(
                "/v1/credit-analysis", json=case.task.model_dump(mode="json")
            )
        assert timeout_response.status_code == 503
        assert timeout_response.json() == {
            "detail": "Authorization dependency timed out"
        }
        assert "identity-provider" not in timeout_response.text
        assert case.tools.calls == []

        error_app = create_app(
            agent,
            scope_resolver=lambda request: case.task.permissions.allowed_scopes,
            task_authorizer=broken_authorizer,
        )
        transport = httpx.ASGITransport(app=error_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            error_response = await client.post(
                "/v1/credit-analysis", json=case.task.model_dump(mode="json")
            )
        assert error_response.status_code == 503
        assert error_response.json() == {"detail": "Authorization dependency failed"}
        assert "identity-provider" not in error_response.text
        assert case.tools.calls == []

    asyncio.run(exercise())


def test_api_rejects_invalid_authorization_timeout_configuration() -> None:
    with pytest.raises(ValueError, match="authorization_timeout_seconds"):
        create_app(authorization_timeout_seconds=0)
