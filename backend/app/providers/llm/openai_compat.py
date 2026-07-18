"""OpenAI-compatible chat-completions provider (FPT AI Marketplace, OpenAI, vLLM...)."""

from __future__ import annotations

import json
import re

import httpx
from pydantic import ValidationError

from app.providers.llm.base import ModelT

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class LLMResponseError(RuntimeError):
    """The upstream model returned output that failed schema validation."""


def extract_json_payload(raw: str) -> str:
    """Lấy khối JSON đầu tiên từ trả lời của model (bỏ code fence nếu có)."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.strip())
    match = _JSON_BLOCK.search(text)
    return match.group(0) if match else text


class OpenAICompatLLMProvider:
    """LLMProvider chạy trên mọi endpoint chat-completions chuẩn OpenAI."""

    def __init__(
        self,
        *,
        provider: str,
        api_url: str,
        api_key: str,
        model_name: str,
        timeout_seconds: float = 90.0,
        temperature: float = 0.2,
    ) -> None:
        self.provider = provider
        self.model_name = model_name
        self.model_version = model_name
        self._temperature = temperature
        self._client = httpx.AsyncClient(
            base_url=api_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
    ) -> ModelT:
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        system = (
            f"{system_prompt}\n\n"
            "Trả lời DUY NHẤT một JSON hợp lệ theo đúng schema sau, "
            f"không kèm bất kỳ văn bản nào khác:\n{schema}"
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        last_error = "no attempt"
        for _ in range(2):
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": self._temperature,
                },
            )
            response.raise_for_status()
            content = str(response.json()["choices"][0]["message"].get("content") or "")
            try:
                return response_model.model_validate_json(extract_json_payload(content))
            except ValidationError as exc:
                last_error = str(exc)
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "JSON vừa rồi không hợp lệ theo schema. Trả lời lại "
                            "DUY NHẤT một JSON hợp lệ, không thêm chữ nào khác."
                        ),
                    }
                )

        raise LLMResponseError(f"Model output failed schema validation: {last_error}")

    async def aclose(self) -> None:
        await self._client.aclose()
