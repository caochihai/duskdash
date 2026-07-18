"""Request contract for the explicitly synthetic agent-design runtime."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class AgentSimulationRunRequest(APIModel):
    objective: str = Field(min_length=1, max_length=2000)

    @field_validator("objective")
    @classmethod
    def normalize_objective(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("objective cannot be empty")
        return normalized
