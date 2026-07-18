"""JWT and principal authorization tests without an identity server."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.dependencies import require_permissions
from app.auth.jwt_validator import JWTValidator, SigningKeyNotFoundError
from app.auth.principal import CurrentPrincipal, EmployeeAccessRecord, build_current_principal
from app.exceptions import AuthenticationError, AuthorizationError


def _b64(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _key_material(kid: str = "unit-key") -> tuple[Any, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64(public_numbers.n),
        "e": _b64(public_numbers.e),
    }
    return private_key, jwk


def _token(
    private_key: Any,
    *,
    kid: str = "unit-key",
    include_nbf: bool = True,
    **overrides: Any,
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": "http://issuer.local/realms/bank-ai",
        "aud": "bank-ai-api",
        "sub": "employee-subject",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "realm_access": {"roles": ["credit_officer"]},
    }
    if include_nbf:
        claims["nbf"] = int((now - timedelta(seconds=1)).timestamp())
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


class FakeJwksProvider:
    def __init__(self, keys: dict[str, dict[str, str]]) -> None:
        self.keys = keys
        self.calls: list[tuple[str, bool]] = []

    async def get_jwk(self, kid: str, *, force_refresh: bool = False) -> dict[str, str]:
        self.calls.append((kid, force_refresh))
        try:
            return self.keys[kid]
        except KeyError as exc:
            raise SigningKeyNotFoundError(kid) from exc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_valid_jwt_checks_signature_and_required_claims() -> None:
    private_key, jwk = _key_material()
    validator = JWTValidator(
        issuer="http://issuer.local/realms/bank-ai",
        audience="bank-ai-api",
        jwks_provider=FakeJwksProvider({"unit-key": jwk}),
        leeway_seconds=0,
    )

    result = await validator.validate(_token(private_key))

    assert result.subject == "employee-subject"
    assert result.realm_roles == frozenset({"credit_officer"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_keycloak_token_without_optional_nbf_is_accepted() -> None:
    private_key, jwk = _key_material()
    validator = JWTValidator(
        issuer="http://issuer.local/realms/bank-ai",
        audience="bank-ai-api",
        jwks_provider=FakeJwksProvider({"unit-key": jwk}),
        leeway_seconds=0,
    )

    result = await validator.validate(_token(private_key, include_nbf=False))

    assert result.subject == "employee-subject"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_future_nbf_is_rejected_when_present() -> None:
    private_key, jwk = _key_material()
    validator = JWTValidator(
        issuer="http://issuer.local/realms/bank-ai",
        audience="bank-ai-api",
        jwks_provider=FakeJwksProvider({"unit-key": jwk}),
        leeway_seconds=0,
    )
    future_nbf = int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())

    with pytest.raises(AuthenticationError):
        await validator.validate(_token(private_key, nbf=future_nbf))


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claim,value",
    [
        ("iss", "http://wrong-issuer.local"),
        ("aud", "wrong-audience"),
        ("sub", ""),
    ],
)
async def test_invalid_required_claim_is_rejected(claim: str, value: str) -> None:
    private_key, jwk = _key_material()
    validator = JWTValidator(
        issuer="http://issuer.local/realms/bank-ai",
        audience="bank-ai-api",
        jwks_provider=FakeJwksProvider({"unit-key": jwk}),
        leeway_seconds=0,
    )

    with pytest.raises(AuthenticationError):
        await validator.validate(_token(private_key, **{claim: value}))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_kid_forces_one_jwks_refresh() -> None:
    private_key, _ = _key_material("missing")
    provider = FakeJwksProvider({})
    validator = JWTValidator(
        issuer="http://issuer.local/realms/bank-ai",
        audience="bank-ai-api",
        jwks_provider=provider,
    )

    with pytest.raises(AuthenticationError, match="signing key"):
        await validator.validate(_token(private_key, kid="missing"))

    assert provider.calls == [("missing", False), ("missing", True)]


@pytest.mark.unit
def test_principal_uses_intersection_of_realm_and_database_roles() -> None:
    record = EmployeeAccessRecord(
        employee_id=uuid4(),
        subject="employee-subject",
        branch_id=uuid4(),
        status="ACTIVE",
        roles=frozenset({"credit_officer", "admin"}),
        permissions=frozenset({"customer:read"}),
    )

    principal = build_current_principal(record, frozenset({"credit_officer"}))

    assert principal.roles == frozenset({"credit_officer"})
    assert principal.permissions == frozenset({"customer:read"})
    assert principal.is_admin is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_permission_dependency_denies_missing_database_permission() -> None:
    principal = CurrentPrincipal(
        employee_id=uuid4(),
        subject="employee-subject",
        branch_id=uuid4(),
        roles=frozenset({"credit_officer"}),
        permissions=frozenset({"customer:read"}),
    )
    dependency = require_permissions("loan:approve")

    with pytest.raises(AuthorizationError):
        await dependency(principal)
