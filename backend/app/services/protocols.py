"""Small structural protocols shared by application services.

Services depend on these contracts rather than concrete SQLAlchemy, Kafka, or
object-storage implementations.  This keeps business rules unit-testable and
prevents routers and agents from issuing SQL directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol
from uuid import UUID


class PrincipalLike(Protocol):
    """Read-only authenticated actor shape accepted by application services."""

    @property
    def employee_id(self) -> UUID: ...

    @property
    def branch_id(self) -> UUID: ...

    @property
    def roles(self) -> frozenset[str] | set[str]: ...

    @property
    def permissions(self) -> frozenset[str] | set[str]: ...

    @property
    def is_admin(self) -> bool: ...


class IdempotencyRepositoryLike(Protocol):
    async def get(
        self,
        *,
        actor_id: UUID,
        operation_name: str,
        idempotency_key: UUID,
    ) -> Mapping[str, Any] | None: ...

    async def create(
        self,
        *,
        actor_id: UUID,
        operation_name: str,
        idempotency_key: UUID,
        request_hash: str,
        response_status: int,
        response_payload: Mapping[str, Any],
        resource_type: str | None,
        resource_id: UUID | None,
    ) -> Mapping[str, Any]: ...


class AuditRepositoryLike(Protocol):
    async def append(
        self,
        *,
        actor_type: str,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        result: str,
        request_id: UUID | None,
        correlation_id: UUID | None,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...
