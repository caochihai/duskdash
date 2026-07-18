"""Safe authenticated-principal contract and persistence adapter protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CurrentPrincipal:
    employee_id: UUID
    subject: str
    branch_id: UUID
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    is_admin: bool = False

    def has_permissions(self, *codes: str) -> bool:
        return self.is_admin or set(codes).issubset(self.permissions)

    def has_any_role(self, *codes: str) -> bool:
        return bool(self.roles.intersection(codes))


@dataclass(frozen=True, slots=True)
class EmployeeAccessRecord:
    """Minimal non-sensitive record returned by the identity repository."""

    employee_id: UUID
    subject: str
    branch_id: UUID
    status: str
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)


class PrincipalResolver(Protocol):
    async def resolve(self, subject: str) -> EmployeeAccessRecord | None:
        """Resolve JWT ``sub`` to the active employee and DB permissions."""


class DenyAllPrincipalResolver:
    """Secure default used until the database adapter is wired."""

    async def resolve(self, subject: str) -> EmployeeAccessRecord | None:
        del subject
        return None


def build_current_principal(
    record: EmployeeAccessRecord,
    realm_roles: frozenset[str],
) -> CurrentPrincipal:
    """Combine Keycloak assertions with roles/permissions stored in PostgreSQL.

    A role is effective only when present in both systems. Permissions remain
    database-derived, preventing a token alone from granting business access.
    """

    effective_roles = record.roles.intersection(realm_roles)
    return CurrentPrincipal(
        employee_id=record.employee_id,
        subject=record.subject,
        branch_id=record.branch_id,
        roles=frozenset(effective_roles),
        permissions=record.permissions,
        is_admin="admin" in effective_roles,
    )
