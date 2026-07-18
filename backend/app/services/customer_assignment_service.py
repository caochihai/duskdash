"""Single-handler customer assignment backed by PostgreSQL and short Redis leases.

PostgreSQL is the authority for who owns a customer.  Redis only proves that
the current handler still owns a short-lived interactive processing lease.
Every new claim/takeover increments ``customer.customer.version`` and uses that
generation in the Redis key, so a stale lease can never authorize work after a
new assignment.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.cache.distributed_lock import RedisDistributedLock
from app.exceptions import ConflictError, NotFoundError
from app.services.access import require_permission, require_role
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike


class CustomerAssignmentRepositoryLike(Protocol):
    async def get_assignment(self, customer_id: UUID) -> Mapping[str, Any] | None: ...

    async def claim_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        expected_version: int,
    ) -> Mapping[str, Any] | None: ...

    async def takeover_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        expected_version: int,
    ) -> Mapping[str, Any] | None: ...

    async def release_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        assignment_version: int,
    ) -> Mapping[str, Any] | None: ...


class CustomerAssignmentService:
    """Coordinate optimistic persistent assignment with owner-token leases."""

    def __init__(
        self,
        repository: CustomerAssignmentRepositoryLike,
        redis: Redis,
        audit: AuditService,
        *,
        lease_ttl_seconds: int = 300,
    ) -> None:
        if lease_ttl_seconds <= 0:
            raise ValueError("customer assignment lease TTL must be positive")
        self._repository = repository
        self._redis = redis
        self._audit = audit
        self._lease_ttl_seconds = lease_ttl_seconds

    @staticmethod
    def _resource(customer_id: UUID, assignment_version: int) -> str:
        return f"customer-assignment:{customer_id}:v{assignment_version}"

    def _new_lock(
        self,
        customer_id: UUID,
        assignment_version: int,
        *,
        owner_token: str | None = None,
    ) -> RedisDistributedLock:
        return RedisDistributedLock(
            self._redis,
            self._resource(customer_id, assignment_version),
            ttl_seconds=self._lease_ttl_seconds,
            owner_token=owner_token,
        )

    def _lease_payload(
        self,
        row: Mapping[str, Any],
        *,
        lease_token: str,
    ) -> dict[str, Any]:
        return {
            "customer_id": row["customer_id"],
            "assigned_employee_id": row["assigned_employee_id"],
            "assignment_version": int(row["assignment_version"]),
            "lease_token": lease_token,
            "lease_ttl_seconds": self._lease_ttl_seconds,
            "lease_expires_at": datetime.now(UTC)
            + timedelta(seconds=self._lease_ttl_seconds),
        }

    async def _state(self, customer_id: UUID) -> Mapping[str, Any]:
        row = await self._repository.get_assignment(customer_id)
        if row is None:
            raise NotFoundError(
                "CUSTOMER_NOT_FOUND",
                "Customer was not found or is outside the authorized scope.",
            )
        return row

    @staticmethod
    def _assignment_conflict(row: Mapping[str, Any]) -> ConflictError:
        assignee = row.get("assigned_employee_id")
        return ConflictError(
            "CUSTOMER_ALREADY_ASSIGNED",
            "The customer is assigned to another employee or has changed.",
            {
                "assigned_employee_id": str(assignee) if assignee is not None else None,
                "current_version": int(row["assignment_version"]),
            },
        )

    async def claim(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        expected_version: int,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        """Claim only when unassigned or already assigned to this employee."""

        require_permission(principal, "customer:read")
        row = await self._repository.claim_assignment(
            customer_id,
            employee_id=principal.employee_id,
            expected_version=expected_version,
        )
        if row is None:
            raise self._assignment_conflict(await self._state(customer_id))

        lock = self._new_lock(customer_id, int(row["assignment_version"]))
        if not await lock.acquire():
            raise ConflictError(
                "CUSTOMER_LEASE_ACTIVE",
                "An active processing lease already exists for this assignment.",
                {"current_version": int(row["assignment_version"])},
            )
        try:
            await self._audit.record(
                principal=principal,
                action="CUSTOMER_ASSIGNMENT_CLAIMED",
                resource_type="CUSTOMER",
                resource_id=customer_id,
                customer_id=customer_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={
                    "assignment_version": int(row["assignment_version"]),
                    "lease_ttl_seconds": self._lease_ttl_seconds,
                },
            )
        except BaseException:
            await lock.release_owned()
            raise
        return self._lease_payload(row, lease_token=lock.owner_token)

    async def heartbeat(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        assignment_version: int,
        lease_token: str,
    ) -> Mapping[str, Any]:
        """Extend only a token owned by the current persistent assignee."""

        require_permission(principal, "customer:read")
        row = await self._state(customer_id)
        if (
            row.get("assigned_employee_id") != principal.employee_id
            or int(row["assignment_version"]) != assignment_version
        ):
            raise self._assignment_conflict(row)

        lock = self._new_lock(
            customer_id,
            assignment_version,
            owner_token=lease_token,
        )
        if not await lock.refresh():
            raise ConflictError(
                "CUSTOMER_LEASE_NOT_OWNED",
                "The processing lease is expired or is not owned by this session.",
            )
        return {
            "customer_id": customer_id,
            "assigned_employee_id": principal.employee_id,
            "assignment_version": assignment_version,
            "lease_ttl_seconds": self._lease_ttl_seconds,
            "lease_expires_at": datetime.now(UTC)
            + timedelta(seconds=self._lease_ttl_seconds),
        }

    async def release(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        assignment_version: int,
        lease_token: str,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        """Release both lease and persistent assignment only for their owner."""

        require_permission(principal, "customer:read")
        row = await self._state(customer_id)
        if (
            row.get("assigned_employee_id") != principal.employee_id
            or int(row["assignment_version"]) != assignment_version
        ):
            raise self._assignment_conflict(row)

        lock = self._new_lock(
            customer_id,
            assignment_version,
            owner_token=lease_token,
        )
        if not await lock.release_owned():
            raise ConflictError(
                "CUSTOMER_LEASE_NOT_OWNED",
                "The processing lease is expired or is not owned by this session.",
            )

        released = await self._repository.release_assignment(
            customer_id,
            employee_id=principal.employee_id,
            assignment_version=assignment_version,
        )
        if released is None:
            raise self._assignment_conflict(await self._state(customer_id))

        try:
            await self._audit.record(
                principal=principal,
                action="CUSTOMER_ASSIGNMENT_RELEASED",
                resource_type="CUSTOMER",
                resource_id=customer_id,
                customer_id=customer_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={"released_assignment_version": assignment_version},
            )
        except BaseException:
            # The enclosing RLS transaction will roll the database release
            # back.  Best-effort restoration avoids leaving that owner with a
            # persistent assignment but no interactive lease.
            await lock.acquire()
            raise
        return {
            "customer_id": customer_id,
            "released_by_employee_id": principal.employee_id,
            "assignment_version": int(released["assignment_version"]),
            "released": True,
        }

    async def takeover(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        expected_version: int,
        reason: str,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        """Allow only a credit manager/admin to replace the current handler."""

        require_permission(principal, "customer:read")
        require_role(principal, "credit_manager", "admin")
        row = await self._repository.takeover_assignment(
            customer_id,
            employee_id=principal.employee_id,
            expected_version=expected_version,
        )
        if row is None:
            raise self._assignment_conflict(await self._state(customer_id))

        lock = self._new_lock(customer_id, int(row["assignment_version"]))
        if not await lock.acquire():
            raise ConflictError(
                "CUSTOMER_LEASE_ACTIVE",
                "An active processing lease already exists for this assignment.",
                {"current_version": int(row["assignment_version"])},
            )
        try:
            await self._audit.record(
                principal=principal,
                action="CUSTOMER_ASSIGNMENT_TAKEN_OVER",
                resource_type="CUSTOMER",
                resource_id=customer_id,
                customer_id=customer_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={
                    "previous_assigned_employee_id": row.get(
                        "previous_assigned_employee_id"
                    ),
                    "new_assigned_employee_id": principal.employee_id,
                    "previous_assignment_version": expected_version,
                    "assignment_version": int(row["assignment_version"]),
                    "reason": reason,
                    "lease_ttl_seconds": self._lease_ttl_seconds,
                },
            )
        except BaseException:
            await lock.release_owned()
            raise
        return self._lease_payload(row, lease_token=lock.owner_token)

    async def assert_can_process(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        lease_token: str | None = None,
    ) -> Mapping[str, Any]:
        """Gate customer mutations/analysis without constraining read-only chat.

        The persistent assignee is always checked.  Interactive callers can
        additionally provide their token, which verifies and refreshes the
        current assignment generation's Redis lease.
        """

        require_permission(principal, "customer:read")
        row = await self._state(customer_id)
        if row.get("assigned_employee_id") != principal.employee_id:
            raise self._assignment_conflict(row)
        if lease_token is not None:
            version = int(row["assignment_version"])
            lock = self._new_lock(customer_id, version, owner_token=lease_token)
            if not await lock.refresh():
                raise ConflictError(
                    "CUSTOMER_LEASE_NOT_OWNED",
                    "The processing lease is expired or is not owned by this session.",
                )
        return row
