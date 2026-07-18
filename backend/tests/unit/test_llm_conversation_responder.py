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
