"""Durable employee notification use cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from app.services.protocols import PrincipalLike


class NotificationRepositoryLike(Protocol):
    async def list(
        self, *, employee_id: UUID, page: int, page_size: int, status: str | None
    ) -> tuple[Sequence[Mapping[str, Any]], int]: ...

    async def mark_read(
        self, notification_id: UUID, *, employee_id: UUID
    ) -> Mapping[str, Any] | None: ...


class NotificationService:
    def __init__(self, repository: NotificationRepositoryLike) -> None:
        self._repository = repository

    async def list(
        self,
        principal: PrincipalLike,
        *,
        page: int,
        page_size: int,
        status: str | None,
    ) -> tuple[Sequence[Mapping[str, Any]], int]:
        if status is not None and status not in {"UNREAD", "READ", "DISMISSED"}:
            raise ValueError("Invalid notification status")
        return await self._repository.list(
            employee_id=principal.employee_id,
            page=page,
            page_size=page_size,
            status=status,
        )

    async def mark_read(
        self, principal: PrincipalLike, notification_id: UUID
    ) -> Mapping[str, Any]:
        row = await self._repository.mark_read(notification_id, employee_id=principal.employee_id)
        if row is None:
            raise LookupError("Notification was not found")
        return row
