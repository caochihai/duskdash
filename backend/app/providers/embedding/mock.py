"""Stable SHAKE-based embeddings for tests and offline development."""

from __future__ import annotations

import hashlib
import math

from app.providers.embedding.base import EmbeddingResult


class MockEmbeddingProvider:
    provider = "mock"
    model_name = "mock-embedding"
    model_version = "1"

    def __init__(self, *, dimension: int = 1024) -> None:
        if dimension < 1:
            raise ValueError("embedding dimension must be positive")
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        vectors = tuple(self._vector(text) for text in texts)
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider,
            model_name=self.model_name,
            model_version=self.model_version,
            dimension=self.dimension,
        )

    def _vector(self, text: str) -> tuple[float, ...]:
        digest = hashlib.shake_256(text.encode()).digest(self.dimension * 2)
        values = [
            (int.from_bytes(digest[index : index + 2], "big") / 32767.5) - 1.0
            for index in range(0, len(digest), 2)
        ]
        magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
        return tuple(value / magnitude for value in values)
