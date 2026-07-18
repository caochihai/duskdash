"""Pure functional-permission helpers."""

from app.auth.principal import CurrentPrincipal


def has_permissions(principal: CurrentPrincipal, *codes: str) -> bool:
    return principal.has_permissions(*codes)


def missing_permissions(principal: CurrentPrincipal, *codes: str) -> frozenset[str]:
    if principal.is_admin:
        return frozenset()
    return frozenset(codes).difference(principal.permissions)
