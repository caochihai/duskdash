from __future__ import annotations

import json
import os
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredLLMClient(Protocol):
    def complete_json(self, *, system_prompt: str, payload: dict, response_model: type[T]) -> T: ...


class AnthropicStructuredClient:
    """Thin Anthropic adapter; all model output is validated by Pydantic."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("Install the 'anthropic' package to use LLM_MODE=anthropic") from exc

        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for LLM_MODE=anthropic")
        resolved_model = model or os.getenv("ANTHROPIC_MODEL")
        if not resolved_model:
            raise RuntimeError("ANTHROPIC_MODEL must be set explicitly for LLM_MODE=anthropic")
        self._client = Anthropic(api_key=resolved_key)
        self._model = resolved_model

    def complete_json(self, *, system_prompt: str, payload: dict, response_model: type[T]) -> T:
        request = {
            "task_input": payload,
            "required_json_schema": response_model.model_json_schema(),
        }
        response = self._client.messages.create(
            model=self._model,
            max_tokens=8192,
            temperature=0,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": "Return only valid JSON matching the supplied schema.\n"
                    + json.dumps(request, ensure_ascii=False, separators=(",", ":")),
                }
            ],
        )
        text_blocks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        if not text_blocks:
            raise ValueError("Anthropic response did not contain a text block")
        raw = "".join(text_blocks).strip()
        if raw.startswith("```"):
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return response_model.model_validate_json(raw)
