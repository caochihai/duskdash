"""Health endpoint schemas."""

from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class LiveResponse(APIModel):
    status: Literal["alive"] = "alive"


class ReadyResponse(APIModel):
    status: Literal["ready", "degraded", "not_ready"]
    dependencies: dict[str, str] = Field(default_factory=dict)
