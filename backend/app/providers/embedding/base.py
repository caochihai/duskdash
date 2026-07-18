"""Embedding provider interface matching pgvector VECTOR(1024)."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class EmbeddingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vectors: tuple[tuple[float, ...], ...]
    provider: str
    model_name: str
    model_version: str
    dimension: int


class EmbeddingProvider(Protocol):
    dimension: int

    async def embed(self, texts: list[str]) -> EmbeddingResult: ...
