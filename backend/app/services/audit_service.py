"""Safe application audit facade."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from app.services.protocols import AuditRepositoryLike, PrincipalLike

_SENSITIVE_KEY = re.compile(
    r"(token|password|secret|authorization|cookie|api[_-]?key|cccd|account[_-]?number|document[_-]?body)",
    re.IGNORECASE,
)


def sanitize_audit_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep small scalar metadata and redact sensitive keys recursively."""

    def clean(value: Any, depth: int) -> Any:
        if depth > 3:
            return "[TRUNCATED]"
        if isinstance(value, Mapping):
            return {
                str(key): "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else clean(item, depth + 1)
                for key, item in list(value.items())[:32]
            }
        if isinstance(value, list):
            return [clean(item, depth + 1) for item in value[:32]]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return str(value)[:512]

    cleaned = clean(metadata or {}, 0)
    return cleaned if isinstance(cleaned, dict) else {}


class AuditService:
    def __init__(self, repository: AuditRepositoryLike) -> None:
        self._repository = repository

    async def record(
        self,
        *,
        principal: PrincipalLike,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        result: str,
        request_id: UUID | None,
        correlation_id: UUID | None,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        return await self._repository.append(
            actor_type="EMPLOYEE",
            actor_id=principal.employee_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            request_id=request_id,
            correlation_id=correlation_id,
            customer_id=customer_id,
            loan_application_id=loan_application_id,
            metadata=sanitize_audit_metadata(metadata),
        )
