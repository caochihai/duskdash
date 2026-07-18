"""Liveness and dependency-aware readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.dependencies import ReadinessProbe
from app.schemas.health import LiveResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LiveResponse, operation_id="health_live")
async def live() -> LiveResponse:
    return LiveResponse()


@router.get("/health/ready", response_model=ReadyResponse, operation_id="health_ready")
async def ready(request: Request, response: Response) -> ReadyResponse:
    probe: ReadinessProbe = request.app.state.readiness_probe
    dependencies = dict(await probe.check())
    required = {"postgres", "kafka", "redis", "minio", "keycloak"}
    required_up = all(dependencies.get(name) == "up" for name in required)
    if not required_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="not_ready", dependencies=dependencies)
    degraded = any(value in {"degraded", "unavailable"} for name, value in dependencies.items() if name not in required)
    return ReadyResponse(status="degraded" if degraded else "ready", dependencies=dependencies)
