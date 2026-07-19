"""Cấu hình OCR worker — đọc từ env."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerSettings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    database_url: str = os.getenv("DATABASE_URL", "")
    ocr_service_url: str = os.getenv("OCR_SERVICE_URL", "http://localhost:8300")
    queue_name: str = os.getenv("OCR_QUEUE_NAME", "ocr")
    max_attempts: int = int(os.getenv("OCR_MAX_ATTEMPTS", "3"))
    ocr_timeout: float = float(os.getenv("OCR_CALL_TIMEOUT", "180"))
