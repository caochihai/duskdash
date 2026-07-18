from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import uuid4

import pytest

from app.agents.base import AgentName
from app.agents.mock_scenarios import (
    MockScenarioCode,
    build_mock_analysis_request,
)
from app.services.agent_simulation_service import AgentSimulationService


def test_mock_scenario_catalog_and_request_ids_are_deterministic() -> None:
    service = AgentSimulationService()

    catalog = service.list_scenarios()

    assert [item.scenario_code for item in catalog] == [
        MockScenarioCode.READY,
        MockScenarioCode.INCOMPLETE,
    ]
    assert all(item.synthetic_data for item in catalog)
    first = build_mock_analysis_request(
        "ready",
        objective="Đánh giá khả năng trả nợ trên dữ liệu mô phỏng",
    )
    second = build_mock_analysis_request(
        MockScenarioCode.READY,
        objective="Đánh giá   khả năng trả nợ trên dữ liệu mô phỏng",
    )
    assert first == second
    assert first.request.document_input.task_id == second.request.document_input.task_id


@pytest.mark.asyncio
async def test_ready_scenario_runs_all_experts_and_returns_numbered_citations() -> None:
    scoped_customer_id = uuid4()
    scoped_loan_id = uuid4()

    result = await AgentSimulationService().run(
        "READY",
        objective="Phân tích khả năng trả nợ",
        customer_id=scoped_customer_id,
        loan_application_id=scoped_loan_id,
    )

    assert result.mode == "MOCK"
    assert result.synthetic_data is True
    assert "DỮ LIỆU MÔ PHỎNG" in result.display_notice
    assert result.customer_id == scoped_customer_id
    assert result.loan_application_id == scoped_loan_id
    assert tuple(output.agent_name for output in result.expert_outputs) == (
        AgentName.DOCUMENT,
        AgentName.CREDIT,
        AgentName.LEGAL_COMPLIANCE,
    )
    assert result.validation.approved_for_synthesis
    assert result.expert_evaluation.approved
    assert result.ready_for_human_review
    assert result.report_writer_executed
    assert result.report_status == "DRAFT"
    assert result.report is not None
    assert result.report.status == "DRAFT"
    assert result.human_decision_required is True
    assert "loan:approve" in result.human_decision_notice

    assert [citation.number for citation in result.citations] == list(
        range(1, len(result.citations) + 1)
    )
    assert all(citation.token == f"[{citation.number}]" for citation in result.citations)
    assert all(citation.source_locator for citation in result.citations)
    assert {citation.citation_type for citation in result.citations} == {
        "EVIDENCE",
        "CALCULATION",
        "POLICY",
    }
    assert result.cited_claims
    assert any(
        finding.finding_type == "DOCUMENT_COMPLETENESS"
        for finding in result.expert_outputs[0].findings
    )
    assert {
        finding.title
        for finding in result.expert_outputs[1].findings
        if finding.finding_type == "REPAYMENT_INDICATOR"
    } == {
        "Persisted DTI indicator",
        "Persisted DSCR indicator",
        "Persisted NET_DISPOSABLE_INCOME indicator",
        "Persisted EXISTING_MONTHLY_OBLIGATIONS indicator",
    }
    assert all(claim.citation_numbers for claim in result.cited_claims)
    assert all(
        f"[{number}]" in claim.rendered_claim
        for claim in result.cited_claims
        for number in claim.citation_numbers
    )
    cited_numbers = {
        number for claim in result.cited_claims for number in claim.citation_numbers
    }
    assert cited_numbers == {citation.number for citation in result.citations}
    assert all(citation.retrieval_mode == "INLINE_MOCK" for citation in result.citations)
    assert all("api_path" not in citation.source_locator for citation in result.citations)
    assert all(citation.quoted_text for citation in result.citations)

    dumped = result.model_dump(mode="json")
    assert not _contains_float(dumped)
    assert not _contains_key(dumped, "loan_decision")


@pytest.mark.asyncio
async def test_incomplete_scenario_is_evaluated_and_never_ready_for_human_review() -> None:
    result = await AgentSimulationService().run(
        MockScenarioCode.INCOMPLETE,
        objective="Kiểm tra hồ sơ thiếu và mâu thuẫn",
    )

    document_output, credit_output, compliance_output = result.expert_outputs
    assert document_output.contradictions
    assert "persisted DSCR calculation" in credit_output.missing_information
    assert compliance_output.findings
    assert "Task was not run" not in credit_output.conclusion
    assert "Task was not run" not in compliance_output.conclusion

    assert not result.validation.approved_for_synthesis
    assert result.validation.validation_status == "INSUFFICIENT_EVIDENCE"
    assert not result.expert_evaluation.approved
    assert result.expert_evaluation.tasks_to_retry
    assert result.expert_evaluation.retry_rounds_used == 1
    assert result.expert_evaluation.retry_limit_reached
    assert not result.ready_for_human_review
    assert not result.report_writer_executed
    assert result.report_status == "INCOMPLETE"
    assert result.report is None
    assert result.cited_claims == ()
    assert "Report Writer" in result.user_summary
    assert "INCOMPLETE" in result.user_summary
    assert result.human_decision_required is True


def test_mock_scenario_rejects_unknown_code_and_empty_objective() -> None:
    with pytest.raises(ValueError, match="unsupported mock scenario"):
        build_mock_analysis_request("UNKNOWN", objective="simulation")
    with pytest.raises(ValueError, match="objective must not be empty"):
        build_mock_analysis_request("READY", objective="   ")


def _contains_float(value: object) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, Mapping):
        return any(_contains_float(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_float(item) for item in value)
    return False


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, Mapping):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_key(item, key) for item in value)
    return False
