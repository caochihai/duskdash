"""Safe request audit adapter; business services emit domain-specific actions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.auth.principal import CurrentPrincipal
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AuditRecord:
    action: str
    result: str
    request_id: UUID
    correlation_id: UUID
    actor_id: UUID | None = None
    resource_type: str = "HTTP_ENDPOINT"
    resource_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditSink(Protocol):
    async def write(self, record: AuditRecord) -> None: ...


class NullAuditSink:
    async def write(self, record: AuditRecord) -> None:
        del record


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        sink: AuditSink = getattr(request.app.state, "audit_sink", NullAuditSink())
        principal = getattr(request.state, "principal", None)
        actor_id = principal.employee_id if isinstance(principal, CurrentPrincipal) else None
        try:
            await sink.write(
                AuditRecord(
                    action="HTTP_REQUEST",
                    result="SUCCESS" if response.status_code < 400 else "FAILURE",
                    request_id=UUID(request.state.request_id),
                    correlation_id=UUID(request.state.correlation_id),
                    actor_id=actor_id,
                    metadata={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    },
                )
            )
        except Exception:
            logger.exception("AUDIT_WRITE_FAILED")
        return response
