"""HTTP API của Deep-Research Engine (Máy 2).

POST /analyze  — Platform giao việc (AnalysisRequest) → nhận AnalysisResponse có nguồn.
GET  /health   — liveness.
"""

from __future__ import annotations

from fastapi import FastAPI

from libs.contracts import AnalysisMode, AnalysisRequest, AnalysisResponse

from . import config
from .orchestrator import run_deep_research

app = FastAPI(title="SHB Deep-Research Engine", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "llm_provider": "mock" if config.use_mock_llm() else config.LLM_PROVIDER,
        "data_provider": config.DATA_PROVIDER,
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    if request.mode == AnalysisMode.SINGLE_AGENT and request.domains:
        # 1 lĩnh vực: vẫn qua orchestrator nhưng chỉ với domain được yêu cầu.
        request = request.model_copy(update={"domains": request.domains[:1]})
    return await run_deep_research(request)
