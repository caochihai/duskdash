"""Defense-in-depth functional permission checks for the service layer."""

from __future__ import annotations

from app.services.protocols import PrincipalLike


def require_permission(principal: PrincipalLike, permission: str) -> None:
    if principal.is_admin:
        return
    if permission not in principal.permissions:
        raise PermissionError(f"Missing permission: {permission}")


def require_any_permission(principal: PrincipalLike, *permissions: str) -> None:
    if principal.is_admin or principal.permissions.intersection(permissions):
        return
    raise PermissionError(f"Missing one of permissions: {', '.join(permissions)}")


def require_role(principal: PrincipalLike, *roles: str) -> None:
    if principal.is_admin or principal.roles.intersection(roles):
        return
    raise PermissionError(f"Missing one of roles: {', '.join(roles)}")

