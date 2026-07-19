from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.agents.context_router import (
    ContextRouter,
    ContextStatus,
    RouteType,
    RoutingRequest,
)


async def _route(
    message: str,
    *,
    include_loan: bool = True,
    attachment_ids: tuple[UUID, ...] = (),
):
    customer_id = uuid4()
    loan_id = uuid4() if include_loan else None
    return await ContextRouter().route(
        RoutingRequest(
            employee_id=uuid4(),
            message=message,
            active_customer_id=customer_id,
            active_loan_application_id=loan_id,
            attachment_ids=attachment_ids,
            accessible_customer_ids=frozenset({customer_id}),
            accessible_loan_ids=frozenset({loan_id}) if loan_id else frozenset(),
        )
    )


@pytest.mark.asyncio
async def test_vietnamese_repayment_question_uses_multi_agent_route() -> None:
    decision = await _route("Đánh giá khả năng trả nợ và DSCR của khách hàng")

    assert decision.intent == "ASSESS_REPAYMENT_CAPACITY"
    assert decision.route_type is RouteType.ORCHESTRATED
    assert decision.required_agents == ("DOCUMENT", "CREDIT", "LEGAL_COMPLIANCE")


@pytest.mark.asyncio
async def test_seal_and_cross_document_question_uses_document_agent() -> None:
    decision = await _route("Kiểm tra xung đột hồ sơ và đã có dấu đỏ chưa")

    assert decision.intent == "REVIEW_DOCUMENTS"
    assert decision.route_type is RouteType.SINGLE_AGENT
    assert decision.required_agents == ("DOCUMENT",)


@pytest.mark.asyncio
async def test_repayment_assessment_requests_missing_loan_context() -> None:
    decision = await _route("Đánh giá khả năng trả nợ của khách hàng", include_loan=False)

    assert decision.intent == "MISSING_CONTEXT"
    assert decision.context_status is ContextStatus.MISSING
    assert decision.missing_context == ("loan_application_id",)
    assert decision.complexity_level == 1


@pytest.mark.asyncio
async def test_definition_question_stays_a_direct_query_without_loan_context() -> None:
    decision = await _route("DTI là gì?", include_loan=False)

    assert decision.intent == "DIRECT_QUERY"
    assert decision.route_type is RouteType.DIRECT
    assert decision.complexity_level == 2


@pytest.mark.asyncio
async def test_explicit_off_topic_question_is_refused_without_fifth_complexity_level() -> None:
    decision = await _route("Hãy kể chuyện cười cho tôi", include_loan=False)

    assert decision.intent == "OUT_OF_SCOPE"
    assert decision.context_status is ContextStatus.OUT_OF_SCOPE
    assert decision.route_type is RouteType.REFUSE
    assert decision.complexity_level == 2


@pytest.mark.asyncio
async def test_policy_question_that_mentions_file_routes_across_domains() -> None:
    decision = await _route("Kiểm tra chính sách tín dụng áp dụng cho hồ sơ này")

    assert decision.intent == "CROSS_DOMAIN_ANALYSIS"
    assert decision.route_type is RouteType.ORCHESTRATED
    assert decision.required_agents == (
        "DOCUMENT",
        "CREDIT",
        "LEGAL_COMPLIANCE",
    )
    assert decision.complexity_level == 4


@pytest.mark.asyncio
async def test_two_domain_question_routes_only_required_experts() -> None:
    decision = await _route("Compare document evidence with the effective policy")

    assert decision.intent == "CROSS_DOMAIN_ANALYSIS"
    assert decision.route_type is RouteType.ORCHESTRATED
    assert decision.required_agents == ("DOCUMENT", "LEGAL_COMPLIANCE")
    assert decision.complexity_level == 4


@pytest.mark.asyncio
async def test_unknown_programming_prompt_is_refused_instead_of_direct() -> None:
    decision = await _route("Write Python code", include_loan=False)

    assert decision.intent == "OUT_OF_SCOPE"
    assert decision.context_status is ContextStatus.OUT_OF_SCOPE
    assert decision.route_type is RouteType.REFUSE
    assert decision.required_agents == ()
    assert 1 <= decision.complexity_level <= 4


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ("What is DTI?", "DTI là gì?"))
async def test_financial_definition_does_not_require_loan_context(question: str) -> None:
    decision = await _route(question, include_loan=False)

    assert decision.context_status is ContextStatus.SUFFICIENT
    assert decision.intent == "DIRECT_QUERY"
    assert decision.route_type is RouteType.DIRECT
    assert decision.missing_context == ()
    assert decision.complexity_level == 2


@pytest.mark.asyncio
async def test_general_financial_definition_does_not_require_customer_context() -> None:
    decision = await ContextRouter().route(
        RoutingRequest(
            employee_id=uuid4(),
            message="What is DSCR?",
        )
    )

    assert decision.context_status is ContextStatus.SUFFICIENT
    assert decision.route_type is RouteType.DIRECT
    assert decision.customer_id is None
    assert decision.loan_application_id is None


@pytest.mark.asyncio
async def test_authorized_attachments_are_preserved_in_routing_decision() -> None:
    attachment_ids = (uuid4(), uuid4())

    decision = await _route(
        "Kiểm tra hồ sơ và dấu đỏ",
        attachment_ids=attachment_ids,
    )

    assert decision.attachment_ids == attachment_ids


@pytest.mark.asyncio
async def test_attachment_caption_without_keywords_routes_to_document_review() -> None:
    """Câu dẫn ngắn khi gửi kèm hồ sơ không được rơi vào nhánh từ chối."""
    decision = await _route(
        "Tôi đã cung cấp thêm 3 hợp đồng",
        include_loan=False,
        attachment_ids=(uuid4(),),
    )

    assert decision.route_type is not RouteType.REFUSE
    assert "DOCUMENT" in decision.required_agents


@pytest.mark.asyncio
async def test_attachment_with_no_matching_keywords_still_reviewed() -> None:
    decision = await _route(
        "Gửi bạn xem thử",
        include_loan=False,
        attachment_ids=(uuid4(),),
    )

    assert decision.route_type is not RouteType.REFUSE
    assert decision.intent == "REVIEW_DOCUMENTS"


@pytest.mark.asyncio
async def test_off_topic_without_attachments_still_refused() -> None:
    decision = await _route("Viết thơ tặng tôi", include_loan=False)

    assert decision.route_type is RouteType.REFUSE
