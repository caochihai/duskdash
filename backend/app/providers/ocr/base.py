"""Structured OCR provider interface."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class OCRPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page_number: int = Field(ge=1)
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pages: tuple[OCRPage, ...]
    provider: str
    model_name: str
    model_version: str


class OCRProvider(Protocol):
    async def extract(self, content: bytes, *, mime_type: str) -> OCRResult: ...
