"""Optional fail-closed FastAPI transport for the standalone Credit Agent."""

from __future__ import annotations

import asyncio
import inspect
import os
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .agent import CreditAgent
from .card import AGENT_ID, get_agent_card
from .demo_tools import DemoCreditTools
from .models import AgentConfig, CreditAnalysisResultV1, CreditTaskInputV1, Permissions


ScopeResolver = Callable[
    [Request], frozenset[str] | set[str] | Awaitable[frozenset[str] | set[str]]
]
TaskAuthorizer = Callable[
    [Request, CreditTaskInputV1], bool | Awaitable[bool]
]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(ApiModel):
    detail: str


class ValidationIssue(ApiModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorResponse(ApiModel):
    detail: list[ValidationIssue]


class HealthResponse(ApiModel):
    status: Literal["ok", "not_configured"]
    agent_id: Literal["credit_agent"]
    runtime_mode: Literal["demo", "injected", "unconfigured"]
    demo_mode: bool
    notice: str


class AgentCardResponse(ApiModel):
    agent_id: Literal["credit_agent"]
    name: str
    version: str
    status: Literal["ONLINE", "OFFLINE"]
    description: str
    capabilities: list[str]
    supported_tasks: list[str]
    allowed_tools: list[str]
    forbidden_actions: list[str]
    input_schema: str
    output_schema: str
    risk_tier: str
    human_approval_required: Literal[True]
    max_tool_calls: int = Field(ge=1, le=20)
    max_follow_up_questions: int = Field(ge=1, le=5)
    timeout_seconds: float = Field(gt=0, le=30)
    audit_required: bool | None = None
    runtime_mode: Literal["demo", "injected", "unconfigured"]
    demo_mode: bool
    runtime_notice: str


async def _trusted_scopes(
    resolver: ScopeResolver, request: Request, timeout_seconds: float
) -> frozenset[str]:
    value = await _run_authorization_callback(
        resolver, request, timeout_seconds=timeout_seconds
    )
    scopes = frozenset(value)
    if not scopes:
        raise HTTPException(status_code=403, detail="No authorized read scopes")
    return scopes


async def _task_is_authorized(
    authorizer: TaskAuthorizer,
    request: Request,
    task: CreditTaskInputV1,
    timeout_seconds: float,
) -> bool:
    value = await _run_authorization_callback(
        authorizer, request, task, timeout_seconds=timeout_seconds
    )
    return value is True


async def _run_authorization_callback(
    callback: Callable[..., object], *args: object, timeout_seconds: float
) -> object:
    """Run a trusted authorization dependency under a bounded request budget.

    Synchronous callbacks run in a worker thread so a slow identity lookup cannot
    block the event loop. They must remain read-only: cancelling the wait does
    not stop an already-running thread.
    """

    if inspect.iscoroutinefunction(callback):
        value = callback(*args)
    else:
        value = await asyncio.wait_for(
            asyncio.to_thread(callback, *args), timeout=timeout_seconds
        )
    if inspect.isawaitable(value):
        return await asyncio.wait_for(value, timeout=timeout_seconds)
    return value


def create_app(
    agent: CreditAgent | None = None,
    *,
    demo_mode: bool = False,
    scope_resolver: ScopeResolver | None = None,
    task_authorizer: TaskAuthorizer | None = None,
    authorization_timeout_seconds: float = 2.0,
) -> FastAPI:
    """Create an API app.

    Production injection requires trusted scope and record-level authorization
    callbacks. Synthetic demo data is enabled only through the explicit
    ``demo_mode=True`` switch.
    """

    if not 0 < authorization_timeout_seconds <= 5:
        raise ValueError("authorization_timeout_seconds must be greater than 0 and at most 5")
    if demo_mode and agent is not None:
        raise ValueError("demo_mode cannot be combined with an injected agent")
    if demo_mode and (scope_resolver is not None or task_authorizer is not None):
        raise ValueError("demo_mode cannot use production authorization callbacks")
    if agent is not None and scope_resolver is None:
        raise ValueError("production agent injection requires scope_resolver")
    if agent is not None and not agent.config.require_audit_sink:
        raise ValueError(
            "production API requires AgentConfig(require_audit_sink=True)"
        )
    if agent is not None and not agent.config.fail_on_audit_error:
        raise ValueError(
            "production API requires AgentConfig(fail_on_audit_error=True)"
        )
    if agent is not None and agent.config.allow_placeholder_policy:
        raise ValueError(
            "production API forbids AgentConfig(allow_placeholder_policy=True)"
        )
    if agent is not None and task_authorizer is None:
        raise ValueError("production agent injection requires task_authorizer")

    active_agent = (
        CreditAgent(
            tools=DemoCreditTools(),
            config=AgentConfig(allow_placeholder_policy=True),
        )
        if demo_mode
        else agent
    )
    configured = active_agent is not None
    runtime_mode = "demo" if demo_mode else ("injected" if configured else "unconfigured")
    runtime_notice = {
        "demo": "Synthetic data and placeholder policy are enabled; not for production decisions.",
        "injected": "Production adapter injected; request scopes are replaced by trusted principal scopes.",
        "unconfigured": "No Credit Agent is configured; analysis endpoint is fail-closed.",
    }[runtime_mode]

    application = FastAPI(
        title="SHB SME Credit Agent API",
        version="1.0.0",
        description="Read-only, human-review-required SME credit analysis transport.",
    )
    application.state.credit_agent = active_agent
    application.state.demo_mode = demo_mode

    @application.middleware("http")
    async def attach_runtime_mode_header(request: Request, call_next: Callable[..., object]):
        response = await call_next(request)
        response.headers["X-Credit-Agent-Mode"] = runtime_mode
        return response

    @application.exception_handler(RequestValidationError)
    async def sanitized_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        safe_errors = [
            {
                "loc": list(error.get("loc", ())),
                "msg": error.get("msg", "Invalid request field"),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": safe_errors})

    @application.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "Agent not configured"}},
        tags=["metadata"],
    )
    async def health() -> JSONResponse:
        payload = {
            "status": "ok" if configured else "not_configured",
            "agent_id": AGENT_ID,
            "runtime_mode": runtime_mode,
            "demo_mode": demo_mode,
            "notice": runtime_notice,
        }
        return JSONResponse(status_code=200 if configured else 503, content=payload)

    @application.get(
        "/agent-card",
        response_model=AgentCardResponse,
        response_model_exclude_none=True,
        tags=["metadata"],
    )
    async def agent_card() -> dict[str, object]:
        card = get_agent_card(
            None if active_agent is None else active_agent.config,
            online=configured,
        )
        card.update(
            {
                "runtime_mode": runtime_mode,
                "demo_mode": demo_mode,
                "runtime_notice": runtime_notice,
            }
        )
        return card

    @application.post(
        "/v1/credit-analysis",
        response_model=CreditAnalysisResultV1,
        responses={
            403: {"model": ErrorResponse, "description": "No authorized read scopes"},
            422: {
                "model": ValidationErrorResponse,
                "description": "Sanitized request validation error",
            },
            503: {
                "model": ErrorResponse,
                "description": "Agent not configured or authorization dependency unavailable",
            },
        },
        tags=["credit-analysis"],
    )
    async def credit_analysis(
        task: CreditTaskInputV1, request: Request
    ) -> CreditAnalysisResultV1:
        if active_agent is None:
            raise HTTPException(status_code=503, detail="Credit Agent is not configured")
        trusted_task = task
        if not demo_mode:
            assert scope_resolver is not None
            assert task_authorizer is not None
            try:
                scopes = await _trusted_scopes(
                    scope_resolver,
                    request,
                    authorization_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Authorization dependency timed out",
                ) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Authorization dependency failed",
                ) from exc
            payload = task.model_dump(mode="python")
            payload["permissions"] = Permissions(allowed_scopes=scopes)
            trusted_task = CreditTaskInputV1.model_validate(payload)
            try:
                authorized = await _task_is_authorized(
                    task_authorizer,
                    request,
                    trusted_task,
                    authorization_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Authorization dependency timed out",
                ) from exc
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Authorization dependency failed",
                ) from exc
            if not authorized:
                raise HTTPException(
                    status_code=403,
                    detail="Task is not authorized for this principal",
                )
        return await active_agent.run(trusted_task)

    default_openapi = application.openapi

    def openapi_with_host_security_boundary() -> dict[str, object]:
        if application.openapi_schema is not None:
            return application.openapi_schema
        schema = default_openapi()
        schema["x-authentication-boundary"] = {
            "provided_by": "host_gateway",
            "package_behavior": (
                "This package does not claim a wire authentication scheme. "
                "Injected scope_resolver and task_authorizer callbacks must derive "
                "authorization from a trusted, authenticated principal."
            ),
        }
        application.openapi_schema = schema
        return schema

    application.openapi = openapi_with_host_security_boundary  # type: ignore[method-assign]
    return application


_DEMO_ENABLED = os.getenv("CREDIT_AGENT_DEMO_MODE", "").strip().lower() in {
    "1",
    "true",
    "yes",
}
app = create_app(demo_mode=_DEMO_ENABLED)
