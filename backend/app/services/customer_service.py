"""Customer use cases; repository RLS remains the final resource boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from app.services.access import require_permission
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike


class CustomerRepositoryLike(Protocol):
    async def list(
        self, *, page: int, page_size: int, search: str | None
    ) -> tuple[Sequence[Mapping[str, Any]], int]: ...

    async def get(self, customer_id: UUID) -> Mapping[str, Any] | None: ...

    async def overview(self, customer_id: UUID) -> Mapping[str, Any] | None: ...

    async def list_documents(self, customer_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def list_loans(self, customer_id: UUID) -> Sequence[Mapping[str, Any]]: ...


class AccountRepositoryLike(Protocol):
    async def for_customer(self, customer_id: UUID) -> Sequence[Mapping[str, Any]]: ...


class CustomerService:
    def __init__(
        self,
        customers: CustomerRepositoryLike,
        accounts: AccountRepositoryLike,
        audit: AuditService | None = None,
    ) -> None:
        self._customers = customers
        self._accounts = accounts
        self._audit = audit

    async def list_customers(
        self,
        principal: PrincipalLike,
        *,
        page: int,
        page_size: int,
        search: str | None,
    ) -> tuple[Sequence[Mapping[str, Any]], int]:
        require_permission(principal, "customer:search")
        return await self._customers.list(page=page, page_size=page_size, search=search)

    async def get_customer(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "customer:read")
        row = await self._customers.get(customer_id)
        if row is None:
            raise LookupError("Customer was not found or is outside the authorized scope")
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="CUSTOMER_VIEWED",
                resource_type="CUSTOMER",
                resource_id=customer_id,
                customer_id=customer_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
            )
        return row

    async def overview(self, principal: PrincipalLike, customer_id: UUID) -> Mapping[str, Any]:
        require_permission(principal, "customer:read")
        row = await self._customers.overview(customer_id)
        if row is None:
            raise LookupError("Customer was not found or is outside the authorized scope")
        return row

    async def accounts(
        self, principal: PrincipalLike, customer_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "account:read")
        return await self._accounts.for_customer(customer_id)

    async def documents(
        self, principal: PrincipalLike, customer_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "document:read")
        return await self._customers.list_documents(customer_id)

    async def loan_applications(
        self, principal: PrincipalLike, customer_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "loan:read")
        return await self._customers.list_loans(customer_id)

