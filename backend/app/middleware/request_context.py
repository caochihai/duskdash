"""Request/trace context propagation without logging query strings or bodies."""

from __future__ import annotations

import re
import time
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging import bind_contextvars, clear_contextvars, get_logger

_TRACEPARENT = re.compile(r"^[\da-f]{2}-([\da-f]{32})-([\da-f]{16})-[\da-f]{2}$", re.IGNORECASE)
logger = get_logger(__name__)


def _safe_uuid(value: str | None) -> str:
    if value:
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return str(uuid4())


def _trace_id(value: str | None) -> str:
    if value:
        match = _TRACEPARENT.fullmatch(value.strip())
        if match and int(match.group(1), 16) != 0:
            return str(UUID(hex=match.group(1)))
    return str(uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _safe_uuid(request.headers.get("X-Request-ID"))
        correlation_id = _safe_uuid(request.headers.get("X-Correlation-ID"))
        trace_id = _trace_id(request.headers.get("traceparent"))
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id
        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            logger.info(
                "HTTP_REQUEST_COMPLETED",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            logger.exception(
                "HTTP_REQUEST_FAILED",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise
        finally:
            clear_contextvars()
