"""Runtime adapter protocols and FastAPI state dependencies."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from fastapi import Request

from app.config import Settings
from app.exceptions import DependencyUnavailableError


class ReadinessProbe(Protocol):
    async def check(self) -> Mapping[str, str]: ...


class RuntimeAdapterLifecycle(Protocol):
    """Cross-slice hook used to initialize DB/Redis/MinIO adapters."""

    async def start(self, application: object, settings: Settings) -> None: ...

    async def stop(self, application: object) -> None: ...


class UnconfiguredReadinessProbe:
    """Secure default: readiness fails until real adapters are installed."""

    async def check(self) -> Mapping[str, str]:
        return {
            "postgres": "not_configured",
            "kafka": "not_configured",
            "redis": "not_configured",
            "minio": "not_configured",
            "keycloak": "not_configured",
            "ocr": "mock",
            "llm": "mock",
        }


def get_runtime_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise DependencyUnavailableError(
            "APPLICATION_NOT_READY",
            "Application configuration is not initialized.",
        )
    return settings
