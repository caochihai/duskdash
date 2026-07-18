from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LLMCallMetric:
    response_model: str
    latency_ms: float
    status_code: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    request_characters: int
    success: bool
    error_type: str | None

    def to_dict(self) -> dict[str, str | int | float | bool | None]:
        return asdict(self)


class GLMStructuredClient:
    """Structured client for GLM through an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 120.0,
        max_tokens: int = 8192,
        thinking: bool | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("GLM_API_KEY") or ""
        self._model = model or os.getenv("GLM_MODEL") or ""
        self._base_url = (base_url or os.getenv("GLM_BASE_URL") or "").rstrip("/")
        if not self._api_key:
            raise RuntimeError("GLM_API_KEY is required for LLM_MODE=glm")
        if not self._model:
            raise RuntimeError("GLM_MODEL is required for LLM_MODE=glm")
        if not self._base_url:
            raise RuntimeError("GLM_BASE_URL is required for LLM_MODE=glm")
        if not self._base_url.startswith(("https://", "http://")):
            raise RuntimeError("GLM_BASE_URL must be an absolute HTTP(S) URL")

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
            transport=transport,
        )
        self._max_tokens = max_tokens
        self._thinking = thinking
        self._call_history: list[LLMCallMetric] = []

    def complete_json(self, *, system_prompt: str, payload: dict, response_model: type[T]) -> T:
        request = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Chỉ trả về JSON hợp lệ, không Markdown, theo JSON Schema sau.\n"
                        + json.dumps(response_model.model_json_schema(), ensure_ascii=False)
                        + "\nDữ liệu cần xử lý:\n"
                        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    ),
                },
            ],
        }
        if self._thinking is not None:
            request["thinking"] = {"type": "enabled" if self._thinking else "disabled"}
        started = perf_counter()
        response: httpx.Response | None = None
        body: dict = {}
        request_characters = len(json.dumps(request, ensure_ascii=False))
        try:
            response = self._client.post("/chat/completions", json=request)
            response.raise_for_status()
            body = response.json()
            try:
                message = body["choices"][0]["message"]
                content = message["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise ValueError("GLM response does not follow the chat-completions contract") from exc
            if not isinstance(content, str) or not content.strip():
                content = message.get("reasoning_content") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                raise ValueError("GLM response did not contain text or reasoning content")
            raw = _extract_json_candidate(_strip_code_fence(content))
            result = response_model.model_validate_json(raw)
        except Exception as exc:
            self._record_metric(
                response_model=response_model.__name__,
                started=started,
                response=response,
                body=body,
                request_characters=request_characters,
                success=False,
                error_type=type(exc).__name__,
            )
            raise
        self._record_metric(
            response_model=response_model.__name__,
            started=started,
            response=response,
            body=body,
            request_characters=request_characters,
            success=True,
            error_type=None,
        )
        return result

    @property
    def call_history(self) -> list[LLMCallMetric]:
        return list(self._call_history)

    def reset_metrics(self) -> None:
        self._call_history.clear()

    def _record_metric(
        self,
        *,
        response_model: str,
        started: float,
        response: httpx.Response | None,
        body: dict,
        request_characters: int,
        success: bool,
        error_type: str | None,
    ) -> None:
        usage = body.get("usage") if isinstance(body, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        self._call_history.append(
            LLMCallMetric(
                response_model=response_model,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                status_code=response.status_code if response is not None else None,
                prompt_tokens=_optional_int(usage.get("prompt_tokens")),
                completion_tokens=_optional_int(usage.get("completion_tokens")),
                total_tokens=_optional_int(usage.get("total_tokens")),
                request_characters=request_characters,
                success=success,
                error_type=error_type,
            )
        )

    def close(self) -> None:
        self._client.close()


def _strip_code_fence(content: str) -> str:
    raw = content.strip()
    if raw.startswith("```"):
        first_newline = raw.find("\n")
        if first_newline != -1:
            raw = raw[first_newline + 1 :]
        if raw.endswith("```"):
            raw = raw[:-3]
    return raw.strip()


def _extract_json_candidate(content: str) -> str:
    if content.startswith("{") and content.endswith("}"):
        return content
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end > start:
        return content[start : end + 1]
    return content


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) else None
