"""Embedding provider contract."""

from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult
from app.providers.embedding.mock import MockEmbeddingProvider

__all__ = ["EmbeddingProvider", "EmbeddingResult", "MockEmbeddingProvider"]
