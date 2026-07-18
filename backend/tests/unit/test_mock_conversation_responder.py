from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.services.mock_conversation_responder import MockConversationResponder


@dataclass(frozen=True, slots=True)
class Principal:
    employee_id: UUID
    branch_id: UUID
    roles: frozenset[str]
    permissions: frozenset[str]
    is_admin: bool = False


def _principal() -> Principal:
    return Principal(
        employee_id=uuid4(),
        branch_id=uuid4(),
        roles=frozenset({"credit_officer"}),
        permissions=frozenset({"loan:analyze"}),
    )


@pytest.mark.asyncio
async def test_mock_responder_refuses_explicit_out_of_scope_request() -> None:
    reply = await MockConversationResponder().respond(
        principal=_principal(),
        conversation={},
        message="Hãy kể chuyện cười",
        route={
            "intent": "OUT_OF_SCOPE",
            "route_type": "REFUSE",
            "complexity_level": 2,
        },
    )

    assert reply.route_type == "REFUSE"
    assert reply.metadata["refused"] is True
    assert "chỉ hỗ trợ nghiệp vụ ngân hàng" in reply.content


@pytest.mark.asyncio
async def test_mock_responder_requests_missing_loan_context() -> None:
    reply = await MockConversationResponder().respond(
        principal=_principal(),
        conversation={"active_customer_id": uuid4()},
        message="Đánh giá khả năng trả nợ",
        route={
            "intent": "MISSING_CONTEXT",
            "route_type": "DIRECT",
            "complexity_level": 1,
            "missing_context": ["loan_application_id"],
        },
    )

    assert "hồ sơ khoản vay" in reply.content
    assert reply.metadata["missing_context"] == ["loan_application_id"]


@pytest.mark.asyncio
async def test_mock_responder_runs_three_experts_and_returns_citation_metadata() -> None:
    customer_id = uuid4()
    loan_id = uuid4()
    reply = await MockConversationResponder().respond(
        principal=_principal(),
        conversation={
            "active_customer_id": customer_id,
            "active_loan_application_id": loan_id,
        },
        message="Phân tích khả năng trả nợ của khoản vay",
        route={
            "intent": "ASSESS_REPAYMENT_CAPACITY",
            "route_type": "ORCHESTRATED",
            "complexity_level": 4,
            "required_agents": ["DOCUMENT", "CREDIT", "LEGAL_COMPLIANCE"],
        },
    )

    assert reply.analysis_case_id is None
    assert reply.metadata["synthetic_analysis_case_id"]
    assert reply.metadata["mode"] == "MOCK"
    assert reply.metadata["report_status"] == "DRAFT"
    assert reply.metadata["report_writer_executed"] is True
    assert reply.metadata["human_decision_required"] is True
    assert reply.metadata["citations"]
    assert "DỮ LIỆU MÔ PHỎNG" in reply.content
    assert "persisted deterministic DTI result is 0.40000000" in reply.content
    assert "Nguồn mô phỏng nội tuyến" in reply.content
    assert "loan:approve" in reply.content


@pytest.mark.asyncio
async def test_mock_responder_marks_conflicted_document_scenario_incomplete() -> None:
    reply = await MockConversationResponder().respond(
        principal=_principal(),
        conversation={
            "active_customer_id": uuid4(),
            "active_loan_application_id": uuid4(),
        },
        message="Kiểm tra hồ sơ thiếu, mâu thuẫn và dấu đỏ",
        route={
            "intent": "REVIEW_DOCUMENTS",
            "route_type": "SINGLE_AGENT",
            "complexity_level": 3,
            "required_agents": ["DOCUMENT"],
        },
    )

    assert reply.metadata["scenario_code"] == "INCOMPLETE"
    assert reply.metadata["report_status"] == "INCOMPLETE"
    assert reply.metadata["report_writer_executed"] is False
    assert reply.metadata["ready_for_human_review"] is False
    assert "không phải hồ sơ khách hàng thật" in reply.content.casefold()
    assert "CHƯA TỔNG HỢP" in reply.content
    assert "Report Writer không được chạy" in reply.content
