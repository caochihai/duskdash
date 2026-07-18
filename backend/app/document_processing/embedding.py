"""Embedding stage that preserves chunk metadata and exact dimension."""

from __future__ import annotations

from app.document_processing.models import ChunkResult
from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult


class ChunkEmbedder:
    def __init__(self, provider: EmbeddingProvider, *, required_dimension: int = 1024) -> None:
        self._provider = provider
        self._required_dimension = required_dimension

    async def embed(self, chunks: tuple[ChunkResult, ...]) -> tuple[tuple[ChunkResult, ...], EmbeddingResult]:
        result = await self._provider.embed([chunk.text_content for chunk in chunks])
        if result.dimension != self._required_dimension:
            raise ValueError(
                f"embedding dimension {result.dimension} does not match VECTOR({self._required_dimension})"
            )
        if len(result.vectors) != len(chunks):
            raise ValueError("embedding provider returned an unexpected vector count")
        embedded = tuple(
            chunk.model_copy(update={"embedding": vector})
            for chunk, vector in zip(chunks, result.vectors, strict=True)
        )
        return embedded, result
