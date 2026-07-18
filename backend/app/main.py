"""FastAPI application factory with graceful adapter lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.api.router import api_router
from app.auth.jwt_validator import CachedJwksClient, JWTValidator
from app.auth.login_rules import LoginRuleEngine
from app.auth.principal import DenyAllPrincipalResolver, PrincipalResolver
from app.config import Settings, get_settings
from app.dependencies import ReadinessProbe, RuntimeAdapterLifecycle, UnconfiguredReadinessProbe
from app.logging import configure_logging, get_logger
from app.middleware.audit import AuditMiddleware, AuditSink, NullAuditSink
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import RuntimeCORSMiddleware, SecurityHeadersMiddleware
from app.runtime_adapters import DefaultRuntimeAdapters

logger = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    jwt_validator: JWTValidator | None = None,
    principal_resolver: PrincipalResolver | None = None,
    readiness_probe: ReadinessProbe | None = None,
    audit_sink: AuditSink | None = None,
    runtime_adapters: RuntimeAdapterLifecycle | None = None,
    storage_adapter: Any | None = None,
    redis_adapter: Any | None = None,
) -> FastAPI:
    """Build an application whose external adapters are explicitly overridable."""

    use_default_runtime = (
        runtime_adapters is None
        and principal_resolver is None
        and readiness_probe is None
        and storage_adapter is None
        and redis_adapter is None
    )
    effective_runtime = DefaultRuntimeAdapters() if use_default_runtime else runtime_adapters

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime_settings = settings or get_settings()
        configure_logging(runtime_settings.log_level, runtime_settings.log_format)
        application.state.settings = runtime_settings
        application.state.shutdown_event = asyncio.Event()
        application.state.principal_resolver = principal_resolver or DenyAllPrincipalResolver()
        application.state.readiness_probe = readiness_probe or UnconfiguredReadinessProbe()
        application.state.audit_sink = audit_sink or NullAuditSink()
        application.state.storage = storage_adapter
        application.state.redis = redis_adapter
        application.state.conversation_responder = None
        application.state.login_rules = LoginRuleEngine.from_settings(runtime_settings)
        if effective_runtime is not None:
            await effective_runtime.start(application, runtime_settings)

        runtime_validator = jwt_validator
        if runtime_validator is None:
            jwks_client = CachedJwksClient(
                runtime_settings.keycloak_jwks_internal_url,
                ttl_seconds=runtime_settings.oidc_jwks_cache_ttl_seconds,
            )
            runtime_validator = JWTValidator(
                issuer=runtime_settings.keycloak_issuer_url,
                audience=runtime_settings.oidc_expected_audience,
                jwks_provider=jwks_client,
                algorithms=runtime_settings.oidc_allowed_algorithms,
                leeway_seconds=runtime_settings.oidc_clock_skew_seconds,
            )
        application.state.jwt_validator = runtime_validator
        logger.info(
            "APPLICATION_STARTED",
            service=runtime_settings.app_name,
            environment=runtime_settings.app_env,
        )
        try:
            yield
        finally:
            application.state.shutdown_event.set()
            await runtime_validator.close()
            if effective_runtime is not None:
                await effective_runtime.stop(application)
            logger.info(
                "APPLICATION_STOPPED",
                service=runtime_settings.app_name,
                environment=runtime_settings.app_env,
            )

    application = FastAPI(
        title="AI Credit Intelligence Workbench API",
        version="1.0.0",
        description="Internal banking API. AI findings support but never make loan decisions.",
        debug=False,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    register_exception_handlers(application)
    application.include_router(api_router)

    # Starlette wraps middleware in reverse registration order. Request context
    # is outermost so every later middleware and exception response has IDs.
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RuntimeCORSMiddleware)
    application.add_middleware(AuditMiddleware)
    application.add_middleware(RequestContextMiddleware)
    return application


app = create_app()


def run() -> None:
    """Console entry point installed as ``bank-api``."""

    import uvicorn

    runtime_settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=runtime_settings.app_host,
        port=runtime_settings.app_port,
        reload=False,
    )
