"""Unit tests for contract-aligned settings."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.config import Settings, get_settings


def valid_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "postgresql://bank_app:unit-test-password@localhost:5432/bank_ai",
        "database_user": "bank_app",
        "kafka_sasl_password": "unit-test-kafka-password",
        "redis_url": "redis://:unit-test-redis-password@localhost:6379/0",
        "minio_internal_endpoint": "http://localhost:9000",
        "minio_public_endpoint": "http://localhost:9000",
        "keycloak_internal_url": "http://localhost:8080",
        "keycloak_public_url": "http://localhost:8080",
        "keycloak_issuer_url": "http://localhost:8080/realms/bank-ai",
        "keycloak_jwks_internal_url": "http://localhost:8080/realms/bank-ai/protocol/openid-connect/certs",
        "keycloak_token_url": "http://localhost:8080/realms/bank-ai/protocol/openid-connect/token",
        "oidc_expected_audience": "bank-ai-api",
        "field_encryption_key": "u" * 32,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.unit
def test_database_contract_scheme_is_normalized() -> None:
    settings = valid_settings()

    assert settings.database_async_url.startswith("postgresql+asyncpg://")
    assert "unit-test-password" not in repr(settings.database_url)


@pytest.mark.unit
def test_required_secrets_have_no_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "DATABASE_URL",
        "KAFKA_SASL_PASSWORD",
        "REDIS_URL",
        "FIELD_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(PydanticValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_comma_separated_contract_lists_are_supported() -> None:
    settings = valid_settings(
        app_cors_origins="http://localhost:3000,http://localhost:3001",
        oidc_allowed_algorithms="RS256",
    )

    assert settings.app_cors_origins == ["http://localhost:3000", "http://localhost:3001"]
    assert settings.oidc_allowed_algorithms == ["RS256"]


@pytest.mark.unit
def test_production_api_rejects_worker_database_role() -> None:
    with pytest.raises(PydanticValidationError, match="bank_app"):
        valid_settings(
            app_env="production",
            app_process_type="api",
            database_user="bank_worker",
            database_url="postgresql://bank_worker:StrongDatabasePass@postgres:5432/bank_ai",
            kafka_security_protocol="SASL_SSL",
            kafka_sasl_password="StrongKafkaPass",
            redis_url="rediss://:StrongRedisPass@redis:6379/0",
            field_encryption_key="z" * 32,
        )


@pytest.mark.unit
def test_production_worker_accepts_worker_database_role_without_minio_credentials() -> None:
    settings = valid_settings(
        app_env="production",
        app_process_type="worker",
        database_user="bank_worker",
        database_url="postgresql://bank_worker:StrongDatabasePass@postgres:5432/bank_ai",
        kafka_security_protocol="SASL_SSL",
        kafka_sasl_username="credit-worker",
        kafka_sasl_password="StrongKafkaPass",
        redis_url="rediss://:StrongRedisPass@redis:6379/0",
        field_encryption_key="z" * 32,
        minio_access_key=None,
        minio_secret_key=None,
    )

    assert settings.database_user == "bank_worker"
    assert settings.minio_secret_key is None


@pytest.mark.unit
def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    environment = {
        "DATABASE_URL": "postgresql://bank_app:cache-test-password@localhost:5432/bank_ai",
        "KAFKA_SASL_PASSWORD": "cache-test-kafka-password",
        "REDIS_URL": "redis://:cache-test-redis-password@localhost:6379/0",
        "MINIO_INTERNAL_ENDPOINT": "http://localhost:9000",
        "MINIO_PUBLIC_ENDPOINT": "http://localhost:9000",
        "KEYCLOAK_INTERNAL_URL": "http://localhost:8080",
        "KEYCLOAK_PUBLIC_URL": "http://localhost:8080",
        "KEYCLOAK_ISSUER_URL": "http://localhost:8080/realms/bank-ai",
        "KEYCLOAK_JWKS_INTERNAL_URL": "http://localhost:8080/realms/bank-ai/protocol/openid-connect/certs",
        "KEYCLOAK_TOKEN_URL": "http://localhost:8080/realms/bank-ai/protocol/openid-connect/token",
        "OIDC_EXPECTED_AUDIENCE": "bank-ai-api",
        "FIELD_ENCRYPTION_KEY": "c" * 32,
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
