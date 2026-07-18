"""Fixture-driven LLM that never makes a network request."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel

from app.providers.llm.base import ModelT


class MockLLMProvider:
    provider = "mock"
    model_name = "mock-llm"
    model_version = "1"

    def __init__(
        self,
        responses: Mapping[str, Mapping[str, Any] | BaseModel | Callable[[str, str], Any]] | None = None,
    ) -> None:
        self._responses = dict(responses or {})

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
    ) -> ModelT:
        response = self._responses.get(response_model.__name__)
        if callable(response):
            response = response(system_prompt, user_prompt)
        if isinstance(response, response_model):
            return response
        if response is None:
            try:
                return response_model()
            except Exception as exc:
                raise ValueError(
                    f"MockLLMProvider requires a fixture for {response_model.__name__}"
                ) from exc
        return response_model.model_validate(response)
