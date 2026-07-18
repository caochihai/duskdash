"""Resource-scope primitives used by service-layer authorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.auth.principal import CurrentPrincipal

ScopeType = Literal["BRANCH", "CUSTOMER", "LOAN_APPLICATION", "ANALYSIS_CASE"]


@dataclass(frozen=True, slots=True)
class ResourceScope:
    scope_type: ScopeType
    scope_id: UUID
    permission_code: str


def scope_allows(
    principal: CurrentPrincipal,
    scopes: tuple[ResourceScope, ...],
    *,
    scope_type: ScopeType,
    scope_id: UUID,
    permission_code: str,
) -> bool:
    if principal.is_admin:
        return True
    return any(
        scope.scope_type == scope_type
        and scope.scope_id == scope_id
        and scope.permission_code == permission_code
        for scope in scopes
    )
