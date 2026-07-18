"""Authorized transaction queries and deterministic summaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from app.services.access import require_permission
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike


class TransactionRepositoryLike(Protocol):
    async def for_customer(
        self,
        customer_id: UUID,
        *,
        date_from: date | None,
        date_to: date | None,
        page: int,
        page_size: int,
    ) -> tuple[Sequence[Mapping[str, Any]], int]: ...

    async def summary(
        self, customer_id: UUID, *, date_from: date | None, date_to: date | None
    ) -> Mapping[str, Any]: ...


class TransactionService:
    def __init__(
        self,
        repository: TransactionRepositoryLike,
        audit: AuditService | None = None,
    ) -> None:
        self._repository = repository
        self._audit = audit

    async def list_transactions(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        date_from: date | None,
        date_to: date | None,
        page: int,
        page_size: int,
        request_id: UUID | None = None,
    ) -> tuple[Sequence[Mapping[str, Any]], int]:
        require_permission(principal, "transaction:read")
        if date_from and date_to and date_to < date_from:
            raise ValueError("date_to must be on or after date_from")
        result = await self._repository.for_customer(
            customer_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="TRANSACTIONS_VIEWED",
                resource_type="CUSTOMER",
                resource_id=customer_id,
                customer_id=customer_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={"date_from": date_from, "date_to": date_to},
            )
        return result

    async def summary(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "transaction:read")
        if date_from and date_to and date_to < date_from:
            raise ValueError("date_to must be on or after date_from")
        return await self._repository.summary(customer_id, date_from=date_from, date_to=date_to)
