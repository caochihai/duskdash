"""Validated runtime configuration aligned with the infrastructure contracts."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_PLACEHOLDER = re.compile(r"(?:<[^>]+>|change[_-]?me|placeholder|example|dummy)", re.IGNORECASE)


class Settings(BaseSettings):
    """Application settings.

    Field names deliberately mirror ``infra/contracts/*.env.example``.  Local
    development uses ``backend/.env.local``; the unrelated ``backend/.env`` is
    never loaded by this application.
    """

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="forbid",
    )

    # Application-only settings.
    app_name: str = "bank-ai-backend"
    app_env: Literal["development", "testing", "production"] = "development"
    app_process_type: Literal["api", "worker", "publisher"] = "api"
    app_host: str = "0.0.0.0"  # noqa: S104 - container bind address
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_debug: bool = False
    app_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Agentic Core Engine (optional; unset keeps deep analysis on the single LLM).
    agent_engine_url: str | None = None
    agent_engine_business_id: str = "B001"
    agent_engine_wait_seconds: int = Field(default=90, ge=10, le=570)

    # Rule-based account gate (all optional; an empty value disables that rule).
    login_rules_deny_usernames: str = ""
    login_rules_allow_username_patterns: str = ""
    login_rules_required_roles: str = ""
    login_rules_access_window_utc: str = ""

    # PostgreSQL contract.
    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "bank_ai"
    database_user: str = "bank_app"
    database_password: SecretStr | None = None
    database_url: SecretStr
    database_pool_size: int = Field(default=20, ge=1, le=100)
    database_pool_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_timeout: int = Field(default=30, ge=1, le=300)
    database_echo: bool = False

    # Kafka contract.
    kafka_bootstrap_servers: str = "localhost:29092"
    kafka_external_bootstrap_servers: str = "localhost:29092"
    kafka_security_protocol: Literal["SASL_PLAINTEXT", "SASL_SSL"] = "SASL_PLAINTEXT"
    kafka_sasl_mechanism: Literal["SCRAM-SHA-512"] = "SCRAM-SHA-512"
    kafka_sasl_username: str = "bank-api"
    kafka_sasl_password: SecretStr
    kafka_client_id: str = "bank-api"
    kafka_consumer_group: str | None = None
    kafka_enable_auto_commit: bool = False
    kafka_auto_offset_reset: Literal["earliest", "latest"] = "earliest"

    # Redis contract.
    redis_host: str = "localhost"
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_password: SecretStr | None = None
    redis_url: SecretStr
    redis_key_prefix: str = "bank-ai"
    redis_socket_timeout: float = Field(default=5.0, gt=0, le=60)
    customer_assignment_lease_ttl_seconds: int = Field(default=300, ge=30, le=3600)

    # MinIO contract. Endpoint values include the http(s) scheme.
    minio_internal_endpoint: str
    minio_public_endpoint: str
    minio_access_key: str | None = None
    minio_secret_key: SecretStr | None = None
    minio_secure: bool = False
    minio_presigned_ttl_seconds: int = Field(default=600, ge=60, le=3600)

    # Keycloak/OIDC contract.
    keycloak_internal_url: str
    keycloak_public_url: str
    keycloak_realm: str = "bank-ai"
    keycloak_issuer_url: str
    keycloak_jwks_internal_url: str
    keycloak_token_url: str
    oidc_expected_audience: str
    oidc_allowed_algorithms: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["RS256"])
    oidc_jwks_cache_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    oidc_clock_skew_seconds: int = Field(default=30, ge=0, le=300)

    # Mock-by-default AI providers. Provider secrets remain optional in mock mode.
    ocr_provider: str = "mock"
    ocr_api_url: str | None = None
    ocr_api_key: SecretStr | None = None
    llm_provider: str = "mock"
    llm_api_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model_name: str = "mock-model"
    vision_model_name: str = "Qwen2.5-VL-7B-Instruct"
    embedding_provider: str = "mock"
    embedding_api_url: str | None = None
    embedding_api_key: SecretStr | None = None
    embedding_dimension: int = Field(default=1024, ge=1)
    embedding_model_name: str = "mock-embedding"

    # Security and logging.
    field_encryption_key: SecretStr
    max_upload_size_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    rate_limit_per_minute: int = Field(default=120, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: Any) -> SecretStr:
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if raw.startswith("postgresql://"):
            raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
        if not raw.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql:// contract scheme")
        return SecretStr(raw)

    @field_validator("redis_url", mode="before")
    @classmethod
    def validate_redis_url(cls, value: Any) -> SecretStr:
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if not raw.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        return SecretStr(raw)

    @field_validator(
        "minio_internal_endpoint",
        "minio_public_endpoint",
        "keycloak_internal_url",
        "keycloak_public_url",
        "keycloak_issuer_url",
        "keycloak_jwks_internal_url",
        "keycloak_token_url",
    )
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("endpoint must be an absolute HTTP(S) URL")
        return value.rstrip("/")

    @field_validator("app_cors_origins", "oidc_allowed_algorithms", mode="before")
    @classmethod
    def parse_string_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: Any) -> str:
        return str(value).upper()

    @model_validator(mode="after")
    def validate_security(self) -> Settings:
        if not self.oidc_allowed_algorithms or any(algorithm != "RS256" for algorithm in self.oidc_allowed_algorithms):
            raise ValueError("OIDC_ALLOWED_ALGORITHMS may only contain RS256")

        if len(self.field_encryption_key.get_secret_value()) < 32:
            raise ValueError("FIELD_ENCRYPTION_KEY must contain at least 32 characters")

        for provider, api_url, api_key in (
            (self.ocr_provider, self.ocr_api_url, self.ocr_api_key),
            (self.llm_provider, self.llm_api_url, self.llm_api_key),
            (self.embedding_provider, self.embedding_api_url, self.embedding_api_key),
        ):
            if provider.lower() != "mock" and (not api_url or api_key is None or not api_key.get_secret_value()):
                raise ValueError(f"Provider {provider!r} requires its API URL and API key")

        if self.app_env != "production":
            return self

        secret_values = {
            "DATABASE_URL": self.database_url.get_secret_value(),
            "REDIS_URL": self.redis_url.get_secret_value(),
            "KAFKA_SASL_PASSWORD": self.kafka_sasl_password.get_secret_value(),
            "FIELD_ENCRYPTION_KEY": self.field_encryption_key.get_secret_value(),
        }
        if self.minio_secret_key is not None:
            secret_values["MINIO_SECRET_KEY"] = self.minio_secret_key.get_secret_value()
        for name, value in secret_values.items():
            if not value or _PLACEHOLDER.search(value):
                raise ValueError(f"Production cannot use a placeholder for {name}")

        if "*" in self.app_cors_origins:
            raise ValueError("Production cannot use wildcard CORS")

        database_username = urlsplit(self.database_url.get_secret_value()).username
        expected_database_user = "bank_worker" if self.app_process_type == "worker" else "bank_app"
        if self.database_user != expected_database_user or database_username != expected_database_user:
            raise ValueError(
                f"Production {self.app_process_type} process must use the {expected_database_user} database role"
            )
        if self.kafka_sasl_username in {"kafka-admin", "admin"}:
            raise ValueError("Production backend cannot use a Kafka admin credential")
        if self.minio_access_key is not None and self.minio_access_key.lower() in {"minioadmin", "root"}:
            raise ValueError("Production backend cannot use a MinIO root credential")
        if self.kafka_security_protocol != "SASL_SSL":
            raise ValueError("Production Kafka connections must use SASL_SSL")
        return self

    @property
    def database_async_url(self) -> str:
        """Return the normalized SQLAlchemy URL without exposing it in reprs."""

        return self.database_url.get_secret_value()

    @property
    def redis_url_value(self) -> str:
        return self.redis_url.get_secret_value()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide immutable-by-convention settings instance."""

    return Settings()
