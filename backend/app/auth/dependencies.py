"""FastAPI authentication and functional-authorization dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_validator import JWTValidator
from app.auth.login_rules import LoginRuleEngine
from app.auth.principal import CurrentPrincipal, PrincipalResolver, build_current_principal
from app.exceptions import AuthenticationError, AuthorizationError, DependencyUnavailableError
from app.logging import bind_contextvars

_bearer = HTTPBearer(auto_error=False, scheme_name="KeycloakBearer")


async def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
) -> CurrentPrincipal:
    """Validate the bearer token and map it to an active employee record."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()

    validator = getattr(request.app.state, "jwt_validator", None)
    resolver = getattr(request.app.state, "principal_resolver", None)
    if not isinstance(validator, JWTValidator) or resolver is None:
        raise DependencyUnavailableError(
            "AUTH_ADAPTER_UNAVAILABLE",
            "Authentication is temporarily unavailable.",
        )

    principal_resolver: PrincipalResolver = resolver
    validated = await validator.validate(credentials.credentials)

    login_rules = getattr(request.app.state, "login_rules", None)
    if isinstance(login_rules, LoginRuleEngine):
        verdict = login_rules.evaluate(
            username=validated.username, roles=validated.realm_roles
        )
        if not verdict.allowed:
            raise AuthenticationError("LOGIN_RULE_DENIED", verdict.reason)

    record = await principal_resolver.resolve(validated.subject)
    if record is None or record.status != "ACTIVE" or record.subject != validated.subject:
        raise AuthenticationError("EMPLOYEE_INACTIVE", "The employee account is not active.")

    principal = build_current_principal(record, validated.realm_roles)
    request.state.principal = principal
    bind_contextvars(actor_id=str(principal.employee_id))
    return principal


def require_permissions(*codes: str) -> Callable[..., Any]:
    """Create a dependency requiring all functional permission codes."""

    required = frozenset(codes)
    if not required or any(not code or ":" not in code for code in required):
        raise ValueError("At least one valid permission code is required")

    async def dependency(
        principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    ) -> CurrentPrincipal:
        missing = required.difference(principal.permissions)
        if missing and not principal.is_admin:
            raise AuthorizationError(
                "MISSING_PERMISSION",
                "You do not have the required permission.",
                {"required": sorted(required)},
            )
        return principal

    return dependency


def require_roles(*roles: str) -> Callable[..., Any]:
    required = frozenset(roles)
    if not required:
        raise ValueError("At least one role is required")

    async def dependency(
        principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    ) -> CurrentPrincipal:
        if not principal.is_admin and not principal.roles.intersection(required):
            raise AuthorizationError(
                "MISSING_ROLE",
                "You do not have the required role.",
                {"required": sorted(required)},
            )
        return principal

    return dependency
