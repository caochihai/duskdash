"""Service-free contract tests for health, errors, auth, and OpenAPI."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from app.compat import UTC
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth.jwt_validator import JWTValidator, SigningKeyNotFoundError
from app.auth.principal import EmployeeAccessRecord
from app.config import Settings
from app.main import create_app
from app.middleware.audit import AuditRecord


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="testing",
        database_url="postgresql://bank_app:test-password@localhost:5432/bank_ai",
        kafka_sasl_password="test-kafka-password",
        redis_url="redis://:test-redis-password@localhost:6379/0",
        minio_internal_endpoint="http://localhost:9000",
        minio_public_endpoint="http://localhost:9000",
        keycloak_internal_url="http://localhost:8080",
        keycloak_public_url="http://localhost:8080",
        keycloak_issuer_url="http://issuer.local/realms/bank-ai",
        keycloak_jwks_internal_url="http://keycloak:8080/realms/bank-ai/protocol/openid-connect/certs",
        keycloak_token_url="http://keycloak:8080/realms/bank-ai/protocol/openid-connect/token",
        oidc_expected_audience="bank-ai-api",
        field_encryption_key="t" * 32,
        log_format="json",
    )


def _b64(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _identity() -> tuple[Any, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    return private_key, {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "contract-key",
        "n": _b64(numbers.n),
        "e": _b64(numbers.e),
    }


class StaticJwks:
    def __init__(self, jwk: dict[str, str]) -> None:
        self.jwk = jwk

    async def get_jwk(self, kid: str, *, force_refresh: bool = False) -> dict[str, str]:
        del force_refresh
        if kid != self.jwk["kid"]:
            raise SigningKeyNotFoundError(kid)
        return self.jwk


class StaticResolver:
    def __init__(self, employee_id: UUID, branch_id: UUID) -> None:
        self.record = EmployeeAccessRecord(
            employee_id=employee_id,
            subject="contract-subject",
            branch_id=branch_id,
            status="ACTIVE",
            roles=frozenset({"credit_officer"}),
            permissions=frozenset({"customer:read", "document:upload"}),
        )

    async def resolve(self, subject: str) -> EmployeeAccessRecord | None:
        return self.record if subject == self.record.subject else None


class ReadyProbe:
    async def check(self) -> dict[str, str]:
        return {
            "postgres": "up",
            "kafka": "up",
            "redis": "up",
            "minio": "up",
            "keycloak": "up",
            "ocr": "mock",
            "llm": "mock",
        }


class CapturingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def write(self, record: AuditRecord) -> None:
        self.records.append(record)


def _token(private_key: Any) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": "http://issuer.local/realms/bank-ai",
            "aud": "bank-ai-api",
            "sub": "contract-subject",
            "iat": int(now.timestamp()),
            "nbf": int((now - timedelta(seconds=1)).timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "realm_access": {"roles": ["credit_officer"]},
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "contract-key"},
    )


@pytest.mark.contract
def test_foundation_http_and_openapi_contract() -> None:
    private_key, jwk = _identity()
    employee_id, branch_id = uuid4(), uuid4()
    audit_sink = CapturingAuditSink()
    validator = JWTValidator(
        issuer="http://issuer.local/realms/bank-ai",
        audience="bank-ai-api",
        jwks_provider=StaticJwks(jwk),
        leeway_seconds=0,
    )
    application = create_app(
        _settings(),
        jwt_validator=validator,
        principal_resolver=StaticResolver(employee_id, branch_id),
        readiness_probe=ReadyProbe(),
        audit_sink=audit_sink,
    )

    with TestClient(application) as client:
        live = client.get("/health/live", headers={"Origin": "http://localhost:3000"})
        assert live.status_code == 200
        assert live.json() == {"status": "alive"}
        assert UUID(live.headers["X-Request-ID"])
        assert live.headers["X-Content-Type-Options"] == "nosniff"
        assert live.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"

        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"

        unauthenticated = client.get("/api/v1/me")
        assert unauthenticated.status_code == 401
        assert set(unauthenticated.json()["error"]) == {"code", "message", "details", "trace_id"}
        assert unauthenticated.headers["WWW-Authenticate"] == "Bearer"

        me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {_token(private_key)}"})
        assert me.status_code == 200
        assert me.json()["employee_id"] == str(employee_id)
        assert me.json()["permissions"] == ["customer:read", "document:upload"]

        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        assert "/health/live" in openapi.json()["paths"]
        assert "/health/ready" in openapi.json()["paths"]
        assert "/api/v1/me" in openapi.json()["paths"]
        assert "/api/v1/agent-simulations/scenarios" in openapi.json()["paths"]
        assert (
            "/api/v1/agent-simulations/scenarios/{scenario_code}/runs"
            in openapi.json()["paths"]
        )
        chat_operation = openapi.json()["paths"][
            "/api/v1/conversations/{conversation_id}/messages"
        ]["post"]
        lease_header = next(
            parameter
            for parameter in chat_operation["parameters"]
            if parameter["name"] == "X-Customer-Assignment-Lease-Token"
        )
        assert lease_header["in"] == "header"
        assert lease_header["required"] is False
        turn_schema = openapi.json()["components"]["schemas"][
            "ConversationTurnResponse"
        ]
        assert {"assistant_message", "reply", "attachment_ids"}.issubset(
            turn_schema["properties"]
        )
        assert (
            "patch"
            in openapi.json()["paths"]["/api/v1/conversations/{conversation_id}"]
        )

    assert audit_sink.records
    assert all("authorization" not in str(record.metadata).lower() for record in audit_sink.records)
