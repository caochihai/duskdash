"""Version-aware policy retrieval with evidence-ready citations."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from rank_bm25 import BM25Okapi

from . import config

_SOURCE_METADATA = {
    "credit_policy.md": {"domain": "credit", "title": "SME Credit Policy", "version": "2026.07", "product_code": "SME_LOAN", "effective_from": "2026-01-01"},
    "compliance_policy.md": {"domain": "compliance", "title": "SME Compliance Policy", "version": "2026.07", "product_code": "SME_LOAN", "effective_from": "2026-01-01"},
    "ops_procedures.md": {"domain": "operations", "title": "SME Operations SOP", "version": "2026.07", "product_code": "SME_LOAN", "effective_from": "2026-01-01"},
    "credit_policy_2026_08.md": {"domain": "credit", "title": "Synthetic SME Credit Policy", "version": "2026.08", "product_code": "SME_LOAN", "effective_from": "2026-08-01"},
}
_DOMAIN_ALIASES = {"ops": "operations", "operations": "operations"}
_INJECTION_PATTERNS = ("ignore previous instructions", "system prompt", "bỏ qua hướng dẫn", "instructions:")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _sections(path: Path) -> list[dict]:
    current = None
    chunks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if current and len(current["text"].strip()) > 40:
                chunks.append(current)
            current = {"section": line[3:].strip(), "text": ""}
        elif current:
            current["text"] += line + "\n"
    if current and len(current["text"].strip()) > 40:
        chunks.append(current)
    return chunks


@lru_cache(maxsize=1)
def _index() -> tuple[BM25Okapi | None, list[dict]]:
    chunks = []
    for path in config.RAG_CORPUS_DIR.glob("*.md"):
        metadata = _SOURCE_METADATA.get(path.name)
        if not metadata:
            continue
        for section in _sections(path):
            text = section["text"].strip()
            chunk_id = hashlib.sha256(f"{path.name}:{section['section']}".encode()).hexdigest()[:16]
            chunks.append({**metadata, "source": path.name, "chunk_id": chunk_id,
                           "section": section["section"], "page": None, "text": text})
    return (BM25Okapi([_tokenize(chunk["text"]) for chunk in chunks]) if chunks else None, chunks)


def search(domain: str, query: str, k: int = 5, product_code: str = "SME_LOAN",
           as_of: date | None = None) -> list[dict]:
    """Return policy passages only when their domain/product/version is effective."""
    resolved_domain = _DOMAIN_ALIASES.get(domain, domain)
    as_of = as_of or date.today()
    bm25, chunks = _index()
    candidates = [chunk for chunk in chunks if chunk["domain"] == resolved_domain
                  and chunk["product_code"] == product_code
                  and date.fromisoformat(chunk["effective_from"]) <= as_of]
    if not bm25 or not candidates:
        return []
    # BM25 scores are calculated on all corpus chunks; preserve their original index.
    scores = bm25.get_scores(_tokenize(query))
    scored = [(float(scores[chunks.index(chunk)]), chunk) for chunk in candidates]
    return [{**chunk, "score": round(score, 3), "quote": chunk["text"][:500],
             "untrusted_content_flag": any(pattern in chunk["text"].lower() for pattern in _INJECTION_PATTERNS)}
            for score, chunk in sorted(scored, key=lambda item: -item[0])[:k] if score > 0]


def reindex() -> None:
    _index.cache_clear()
    _index()


def citation(hit: dict) -> dict:
    return {key: hit[key] for key in ("title", "version", "section", "page", "chunk_id", "quote")}
