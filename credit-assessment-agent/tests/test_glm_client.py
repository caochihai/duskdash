from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.llm_client.glm_client import GLMStructuredClient


class ExampleResponse(BaseModel):
    verdict: str
    score: int


def test_glm_client_parses_structured_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "glm-test"
        assert body["response_format"] == {"type": "json_object"}
        assert "thinking" not in body
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"verdict":"PASS","score":9}'}}]},
        )

    client = GLMStructuredClient(
        api_key="test-key",
        model="glm-test",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    result = client.complete_json(
        system_prompt="Evaluate",
        payload={"tests": 17},
        response_model=ExampleResponse,
    )
    assert result == ExampleResponse(verdict="PASS", score=9)
    assert len(client.call_history) == 1
    assert client.call_history[0].success is True
    assert client.call_history[0].status_code == 200
    client.close()


def test_glm_client_accepts_json_code_fence():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": "```json\n{\"verdict\":\"PASS\",\"score\":8}\n```"}}]},
        )
    )
    client = GLMStructuredClient(
        api_key="test-key",
        model="glm-test",
        base_url="https://example.test/v1",
        transport=transport,
    )
    assert client.complete_json(
        system_prompt="Evaluate", payload={}, response_model=ExampleResponse
    ).score == 8
    client.close()


def test_glm_client_accepts_json_from_reasoning_content_when_content_is_empty():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": 'Kết quả JSON: {"verdict":"PASS","score":7}',
                        }
                    }
                ]
            },
        )
    )
    client = GLMStructuredClient(
        api_key="test-key",
        model="glm-test",
        base_url="https://example.test/v1",
        transport=transport,
    )
    assert client.complete_json(
        system_prompt="Evaluate", payload={}, response_model=ExampleResponse
    ).score == 7
    client.close()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"api_key": "", "model": "m", "base_url": "https://x.test"}, "GLM_API_KEY"),
        ({"api_key": "k", "model": "", "base_url": "https://x.test"}, "GLM_MODEL"),
        ({"api_key": "k", "model": "m", "base_url": ""}, "GLM_BASE_URL"),
        ({"api_key": "k", "model": "m", "base_url": "x.test"}, "absolute"),
    ],
)
def test_glm_client_rejects_incomplete_configuration(monkeypatch, kwargs, message):
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    monkeypatch.delenv("GLM_MODEL", raising=False)
    monkeypatch.delenv("GLM_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match=message):
        GLMStructuredClient(**kwargs)
