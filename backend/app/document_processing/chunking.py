"""Deterministic word-window chunking for RAG preparation."""

from __future__ import annotations

from app.document_processing.models import ChunkResult, PageResult


class DocumentChunker:
    def __init__(self, *, max_tokens: int = 200, overlap_tokens: int = 20) -> None:
        if max_tokens < 1 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
            raise ValueError("chunk limits are invalid")
        self._max_tokens = max_tokens
        self._stride = max_tokens - overlap_tokens

    async def chunk(self, pages: tuple[PageResult, ...]) -> tuple[ChunkResult, ...]:
        chunks: list[ChunkResult] = []
        for page in pages:
            words = page.text_content.split()
            for start in range(0, len(words), self._stride):
                window = words[start : start + self._max_tokens]
                if not window:
                    continue
                chunks.append(
                    ChunkResult(
                        chunk_index=len(chunks),
                        page_from=page.page_number,
                        page_to=page.page_number,
                        text_content=" ".join(window),
                        token_count=len(window),
                        metadata={"page_number": page.page_number},
                    )
                )
                if start + self._max_tokens >= len(words):
                    break
        return tuple(chunks)
