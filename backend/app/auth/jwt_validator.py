"""Offline Keycloak JWT validation with bounded JWKS caching."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt

from app.exceptions import AuthenticationError


class SigningKeyNotFoundError(Exception):
    pass


class JwksProvider(Protocol):
    async def get_jwk(self, kid: str, *, force_refresh: bool = False) -> Mapping[str, Any]: ...


class CachedJwksClient:
    """Small async JWKS client; it never caches access tokens or credentials."""

    def __init__(
        self,
        url: str,
        *,
        ttl_seconds: int = 300,
        timeout_seconds: float = 5.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = http_client is None
        self._keys: dict[str, Mapping[str, Any]] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _refresh(self) -> None:
        response = await self._client.get(self._url, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        keys = payload.get("keys") if isinstance(payload, dict) else None
        if not isinstance(keys, list):
            raise AuthenticationError("JWKS_INVALID", "The identity provider returned invalid key data.")
        parsed: dict[str, Mapping[str, Any]] = {}
        for key in keys:
            if isinstance(key, dict) and isinstance(key.get("kid"), str):
                parsed[key["kid"]] = key
        self._keys = parsed
        self._expires_at = time.monotonic() + self._ttl_seconds

    async def get_jwk(self, kid: str, *, force_refresh: bool = False) -> Mapping[str, Any]:
        async with self._lock:
            if force_refresh or time.monotonic() >= self._expires_at or not self._keys:
                try:
                    await self._refresh()
                except AuthenticationError:
                    raise
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    raise AuthenticationError(
                        "JWKS_UNAVAILABLE",
                        "Identity verification keys are temporarily unavailable.",
                    ) from exc
            key = self._keys.get(kid)
            if key is None:
                raise SigningKeyNotFoundError(kid)
            return key

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


@dataclass(frozen=True, slots=True)
class ValidatedToken:
    subject: str
    realm_roles: frozenset[str]
    issuer: str
    audience: tuple[str, ...]
    issued_at: int
    expires_at: int
    token_id: str | None = None
    session_id: str | None = None
    username: str | None = None


class JWTValidator:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_provider: JwksProvider,
        algorithms: Sequence[str] = ("RS256",),
        leeway_seconds: int = 30,
    ) -> None:
        if not algorithms or any(algorithm != "RS256" for algorithm in algorithms):
            raise ValueError("Only RS256 is supported")
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks_provider = jwks_provider
        self._algorithms = tuple(algorithms)
        self._leeway_seconds = leeway_seconds

    async def _resolve_key(self, kid: str) -> Any:
        try:
            jwk = await self._jwks_provider.get_jwk(kid)
        except SigningKeyNotFoundError:
            try:
                jwk = await self._jwks_provider.get_jwk(kid, force_refresh=True)
            except SigningKeyNotFoundError as exc:
                raise AuthenticationError(
                    "TOKEN_KEY_NOT_FOUND",
                    "The token signing key is not recognized.",
                ) from exc
        try:
            return jwt.PyJWK.from_dict(dict(jwk), algorithm="RS256").key
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise AuthenticationError("JWKS_INVALID", "The token signing key is invalid.") from exc

    async def validate(self, token: str) -> ValidatedToken:
        if not token or len(token) > 16_384:
            raise AuthenticationError("TOKEN_INVALID", "The access token is invalid.")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("TOKEN_INVALID", "The access token is invalid.") from exc

        kid = header.get("kid")
        algorithm = header.get("alg")
        if not isinstance(kid, str) or not kid or algorithm not in self._algorithms:
            raise AuthenticationError("TOKEN_INVALID", "The access token header is invalid.")

        key = await self._resolve_key(kid)
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(self._algorithms),
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway_seconds,
                options={
                    # Keycloak access tokens do not always include ``nbf``.
                    # PyJWT still validates it when present through verify_nbf.
                    "require": ["iss", "aud", "exp", "iat", "sub"],
                    "verify_signature": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("TOKEN_EXPIRED", "The access token has expired.") from exc
        except jwt.ImmatureSignatureError as exc:
            raise AuthenticationError("TOKEN_NOT_ACTIVE", "The access token is not active.") from exc
        except jwt.PyJWTError as exc:
            raise AuthenticationError("TOKEN_INVALID", "The access token is invalid.") from exc

        subject = claims.get("sub")
        issued_at = claims.get("iat")
        expires_at = claims.get("exp")
        if (
            not isinstance(subject, str)
            or not subject
            or not isinstance(issued_at, int)
            or not isinstance(expires_at, int)
        ):
            raise AuthenticationError("TOKEN_INVALID", "The access token claims are invalid.")

        realm_access = claims.get("realm_access", {})
        roles_value = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
        if not isinstance(roles_value, list) or any(not isinstance(role, str) for role in roles_value):
            raise AuthenticationError("TOKEN_INVALID", "The access token roles are invalid.")
        audience_value = claims.get("aud")
        if isinstance(audience_value, str):
            audiences = (audience_value,)
        elif isinstance(audience_value, list) and all(
            isinstance(audience, str) for audience in audience_value
        ):
            audiences = tuple(audience_value)
        else:
            raise AuthenticationError("TOKEN_INVALID", "The token audience is invalid.")
        return ValidatedToken(
            subject=subject,
            realm_roles=frozenset(roles_value),
            issuer=str(claims["iss"]),
            audience=audiences,
            issued_at=issued_at,
            expires_at=expires_at,
            token_id=claims.get("jti") if isinstance(claims.get("jti"), str) else None,
            session_id=claims.get("sid") if isinstance(claims.get("sid"), str) else None,
            username=claims.get("preferred_username")
            if isinstance(claims.get("preferred_username"), str)
            else None,
        )

    async def close(self) -> None:
        close_method = getattr(self._jwks_provider, "close", None)
        if close_method is not None:
            await close_method()
