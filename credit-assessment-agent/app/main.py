from __future__ import annotations

import os

from fastapi import FastAPI
from dotenv import load_dotenv

from app.agents.chief_reviewer import ChiefCreditReviewerAgent
from app.agents.document_auditor import DocumentAuditorAgent
from app.api.v1 import assess, health
from app.llm_client.anthropic_client import AnthropicStructuredClient
from app.llm_client.glm_client import GLMStructuredClient
from app.observability.tracing import configure_logging
from app.orchestration.pipeline import AssessmentPipeline


def create_app(*, pipeline: AssessmentPipeline | None = None) -> FastAPI:
    load_dotenv(override=False)
    configure_logging()
    app = FastAPI(
        title="Credit Document Assessment Agent",
        version="0.1.0",
        description="Human-in-the-loop credit document assessment microservice",
    )
    app.state.pipeline = pipeline or _build_pipeline_from_environment()
    app.include_router(health.router)
    app.include_router(assess.router)
    return app


def _build_pipeline_from_environment() -> AssessmentPipeline:
    mode = os.getenv("LLM_MODE", "deterministic").lower()
    if mode == "anthropic":
        client = AnthropicStructuredClient()
        return AssessmentPipeline(
            auditor=DocumentAuditorAgent(client),
            reviewer=ChiefCreditReviewerAgent(client),
        )
    if mode == "glm":
        client = GLMStructuredClient()
        return AssessmentPipeline(
            auditor=DocumentAuditorAgent(client),
            reviewer=ChiefCreditReviewerAgent(client),
        )
    if mode != "deterministic":
        raise RuntimeError("LLM_MODE must be 'deterministic', 'anthropic', or 'glm'")
    return AssessmentPipeline()


app = create_app()
