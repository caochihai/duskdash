"""Unit tests for the real-LLM conversation responder and JSON extraction."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.providers.llm.openai_compat import extract_json_payload
from app.services.llm_conversation_responder import LLMConversationResponder


class _Answer(BaseModel):
    content: str


def test_extract_json_payload_strips_code_fences() -> None:
    raw = '```json\n{"content": "xin chào"}\n```'
    assert extract_json_payload(raw) == '{"content": "xin chào"}'


def test_extract_json_payload_finds_embedded_object() -> None:
    raw = 'Đây là kết quả: {"content": "ok"} — hết.'
    assert extract_json_payload(raw) == '{"content": "ok"}'


class _StubLLM:
    provider = "stub"
    model_name = "stub-model"
    model_version = "stub-model"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def generate_structured(self, *, system_prompt, user_prompt, response_model):
        self.calls += 1
        if self.fail:
            raise RuntimeError("upstream down")
        return response_model(content="Trả lời từ stub [nguồn: transaction_summary]")


def _principal() -> SimpleNamespace:
    return SimpleNamespace(employee_id=uuid4(), branch_id=uuid4(), is_admin=False)


@pytest.mark.asyncio
async def test_refuse_route_never_calls_llm() -> None:
    llm = _StubLLM()
    responder = LLMConversationResponder(llm)
    reply = await responder.respond(
        principal=_principal(),
        conversation={},
        message="hack hộ tôi",
        route={"route_type": "REFUSE", "intent": "OUT_OF_SCOPE"},
    )
    assert llm.calls == 0
    assert "không xử lý" in reply.content
    assert reply.metadata["responder"] == "llm"


@pytest.mark.asyncio
async def test_llm_failure_returns_degraded_reply_instead_of_raising() -> None:
    responder = LLMConversationResponder(_StubLLM(fail=True))
    reply = await responder.respond(
        principal=_principal(),
        conversation={},
        message="khách hàng này có bao nhiêu giao dịch?",
        route={"route_type": "DIRECT", "intent": "DIRECT_QUERY"},
    )
    assert reply.metadata.get("degraded") is True
    assert reply.content


def test_render_highlight_markdown_levels_and_links() -> None:
    from app.services.document_highlight_service import (
        AnnotatedImage,
        HighlightResult,
        HighlightSegment,
        render_highlight_markdown,
    )

    result = HighlightResult(
        document_summary="Giấy đăng ký kinh doanh công ty TNHH ABC.",
        answer="Hồ sơ hợp lệ nhưng có một điểm lệch.",
        segments=[
            HighlightSegment(
                document_index=0,
                text="Số CCCD 001199001234",
                level="critical",
                reason="Khác với số CCCD trong hệ thống",
                bbox_2d=[100, 200, 500, 260],
            ),
            HighlightSegment(
                document_index=0,
                text="Vốn điều lệ 5 tỷ đồng",
                level="emphasis",
                reason="Liên quan trực tiếp câu hỏi về hạn mức",
            ),
        ],
    )
    links = [AnnotatedImage(key="highlights/c/x-0.jpg", url="https://minio/presigned/x")]
    content = render_highlight_markdown(result, links)
    assert "🔴 **[CẢNH BÁO]**" in content
    assert "🟡 **[NHẤN MẠNH]**" in content
    assert "Khác với số CCCD" in content
    # Ảnh highlight đi qua metadata.highlight_documents (gallery), không chèn
    # link vào text để chat giữ vai trò tương tác thuần.
    assert "https://minio/presigned/x" not in content


@pytest.mark.asyncio
async def test_attachments_without_db_fall_back_to_single_llm() -> None:
    from app.services.document_highlight_service import DocumentHighlighter

    class _NoCallVision:
        provider = "stub"
        model_name = "stub-vl"
        model_version = "stub-vl"

        async def generate_structured(self, **kwargs):
            raise AssertionError("không được gọi vision khi chưa đọc được file")

    class _NoCallStorage:
        async def get_object(self, *a, **k):
            raise AssertionError("DB factory=None thì không tới bước storage")

    llm = _StubLLM()
    responder = LLMConversationResponder(
        llm,
        highlighter=DocumentHighlighter(_NoCallVision(), None),
        storage=_NoCallStorage(),
    )
    reply = await responder.respond(
        principal=_principal(),
        conversation={},
        message="kiểm tra hồ sơ đính kèm",
        route={"route_type": "DIRECT", "intent": "DIRECT_QUERY"},
        attachment_ids=(uuid4(),),
    )
    assert llm.calls == 1
    assert reply.metadata.get("attachments_used_for_llm_analysis") is False


class _StubEngine:
    def __init__(self) -> None:
        self.case = {
            "state": "Pending Approval",
            "package": {
                "recommendation": "Đồng ý có điều kiện",
                "proposed_limit": 4_200_000_000.0,
                "plan_version": 2,
                "conditions": ["Bổ sung BCTC quý gần nhất"],
                "verdicts": [
                    {"agent": "credit", "decision": "approve", "summary": "DSCR đạt"},
                    {"agent": "validation", "decision": "flag", "summary": "LTV vượt trần"},
                ],
                "trace_summary": ["Planner sinh DAG 5 task"],
            },
        }

    async def create_case(self, request, documents=None, submitted_by="platform"):
        self.request = request
        return "case_test_1"

    async def run(self, case_id):
        return None

    async def wait_final(self, case_id, timeout_s=90):
        return "Pending Approval"

    async def get_case(self, case_id):
        return self.case


@pytest.mark.asyncio
async def test_orchestrated_route_uses_agent_engine() -> None:
    llm = _StubLLM()
    engine = _StubEngine()
    responder = LLMConversationResponder(llm, engine=engine)
    reply = await responder.respond(
        principal=_principal(),
        conversation={},
        message="Phân tích khoản vay của khách hàng này",
        route={"route_type": "ORCHESTRATED", "intent": "LOAN_ANALYSIS"},
    )
    assert llm.calls == 0
    assert reply.metadata["engine"] == "agent_engine"
    assert reply.metadata["engine_case_id"] == "case_test_1"
    assert "Đồng ý có điều kiện" in reply.content
    assert "credit" in reply.content and "validation" in reply.content
    assert "4,200,000,000" in reply.content


@pytest.mark.asyncio
async def test_direct_route_never_touches_engine() -> None:
    class _ExplodingEngine:
        async def create_case(self, *a, **k):
            raise AssertionError("engine must not be called for DIRECT routes")

    responder = LLMConversationResponder(_StubLLM(), engine=_ExplodingEngine())
    reply = await responder.respond(
        principal=_principal(),
        conversation={},
        message="số dư của khách?",
        route={"route_type": "DIRECT", "intent": "DIRECT_QUERY"},
    )
    assert reply.metadata.get("engine") is None


@pytest.mark.asyncio
async def test_engine_failure_falls_back_to_single_llm() -> None:
    class _BrokenEngine:
        async def create_case(self, *a, **k):
            raise RuntimeError("engine down")

    llm = _StubLLM()
    responder = LLMConversationResponder(llm, engine=_BrokenEngine())
    reply = await responder.respond(
        principal=_principal(),
        conversation={},
        message="Phân tích khoản vay",
        route={"route_type": "ORCHESTRATED", "intent": "LOAN_ANALYSIS"},
    )
    assert llm.calls == 1
    assert reply.metadata.get("engine") is None


@pytest.mark.asyncio
async def test_successful_reply_carries_model_metadata() -> None:
    responder = LLMConversationResponder(_StubLLM())
    reply = await responder.respond(
        principal=_principal(),
        conversation={},
        message="tổng quan khách hàng?",
        route={"route_type": "DIRECT", "intent": "DIRECT_QUERY", "complexity_level": 1},
    )
    assert "stub" == reply.metadata["provider"]
    assert reply.complexity_level == 1
    assert "[nguồn:" in reply.content
