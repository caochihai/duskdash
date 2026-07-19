"""Cấu hình Engine — đọc từ env, có mặc định chạy được offline (mock)."""

from __future__ import annotations

import os

# --- LLM ---
# LLM_PROVIDER=mock → không gọi mạng, sinh văn xuôi tất định (test/CI/demo offline).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://mkp-api.fptcloud.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-oss-120b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

# --- Nguồn dữ liệu khách (Data API của Platform) ---
# DATA_PROVIDER=mock → dùng fixture in-memory (Engine chạy standalone không cần Platform).
DATA_PROVIDER = os.getenv("DATA_PROVIDER", "mock").lower()
PLATFORM_DATA_URL = os.getenv("PLATFORM_DATA_URL", "http://platform:8100")
PLATFORM_SERVICE_TOKEN = os.getenv("PLATFORM_SERVICE_TOKEN", "")

# --- Deep-research ---
MAX_EVAL_ROUNDS = int(os.getenv("ENGINE_MAX_EVAL_ROUNDS", "1"))
SPECIALIST_TIMEOUT = float(os.getenv("ENGINE_SPECIALIST_TIMEOUT", "45"))


def use_mock_llm() -> bool:
    return LLM_PROVIDER == "mock" or not LLM_API_KEY
