"""Cấu hình OCR service — đọc từ env, không hardcode secret.

Model chạy qua API remote (Azure), KHÔNG chạy local. `OCR_PROVIDER=mock` để
chạy/test không cần Azure (sinh bbox giả nhưng hợp lệ, đủ để highlight end-to-end).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OcrSettings:
    provider: str = os.getenv("OCR_PROVIDER", "mock").lower()          # "azure" | "mock"
    azure_endpoint: str = os.getenv("AZURE_DI_ENDPOINT", "")
    azure_key: str = os.getenv("AZURE_DI_KEY", "")
    azure_model: str = os.getenv("AZURE_DI_MODEL", "prebuilt-read")
    azure_api_version: str = os.getenv("AZURE_DI_API_VERSION", "2024-11-30")
    poll_interval: float = float(os.getenv("OCR_POLL_INTERVAL", "1.5"))
    poll_timeout: float = float(os.getenv("OCR_POLL_TIMEOUT", "120"))
    http_timeout: float = float(os.getenv("OCR_HTTP_TIMEOUT", "60"))

    def validate_for_azure(self) -> None:
        if self.provider == "azure" and (not self.azure_endpoint or not self.azure_key):
            raise RuntimeError(
                "OCR_PROVIDER=azure nhưng thiếu AZURE_DI_ENDPOINT/AZURE_DI_KEY"
            )
