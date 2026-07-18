"""Application configuration using Pydantic Settings.

Reads environment variables matching the infra connection contracts.
Validates that production environments do not run with placeholder secrets,
wildcard CORS, or missing JWT issuer/audience.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Groups: App, Database, Redis, Kafka, MinIO, Keycloak/OIDC,
    OCR, LLM, Embedding, Security, Logging.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────
    app_name: str = Field(default="bank-ai-backend")
    app_env: str = Field(default="development")
    app_port: int = Field(default=8000)
    app_cors_origins: list[str] = Field(default=["http://localhost:3000"])
    app_debug: bool = Field(default=False)

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://bank_app:changeme@localhost:5432/bank_ai",
    )
    database_pool_size: int = Field(default=20)
    database_pool_max_overflow: int = Field(default=10)
    database_pool_timeout: int = Field(default=30)
    database_echo: bool = Field(default=False)

    # ── Redis ────────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://:changeme@localhost:6379/0",
    )
    redis_key_prefix: str = Field(default="bank-ai")
    redis_socket_timeout: float = Field(default=5.0)

    # ── Kafka ────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = Field(default="localhost:29092")
    kafka_security_protocol: str = Field(default="SASL_PLAINTEXT")
    kafka_sasl_mechanism: str = Field(default="SCRAM-SHA-512")
    kafka_sasl_username: str = Field(default="bank-api")
    kafka_sasl_password: SecretStr = Field(default=SecretStr("changeme"))
    kafka_client_id: str = Field(default="bank-api")
    kafka_enable_auto_commit: bool = Field(default=False)
    kafka_auto_offset_reset: str = Field(default="earliest")

    # ── MinIO ────────────────────────────────────────────────────────────
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="bank-api")
    minio_secret_key: SecretStr = Field(default=SecretStr("changeme"))
    minio_secure: bool = Field(default=False)
    minio_presigned_ttl_seconds: int = Field(default=600)
    minio_public_endpoint: str = Field(default="http://localhost:9000")

    # ── Keycloak / OIDC ─────────────────────────────────────────────────
    keycloak_issuer_url: str = Field(
        default="http://localhost:8080/realms/bank-ai",
    )
    keycloak_jwks_url: str = Field(
        default="http://localhost:8080/realms/bank-ai/protocol/openid-connect/certs",
    )
    oidc_expected_audience: str = Field(default="bank-ai-api")
    keycloak_public_url: str = Field(default="http://localhost:8080")
    keycloak_realm: str = Field(default="bank-ai")

    # ── OCR Provider ─────────────────────────────────────────────────────
    ocr_provider: str = Field(default="mock")
    ocr_api_url: str = Field(default="")
    ocr_api_key: SecretStr = Field(default=SecretStr(""))

    # ── LLM Provider ─────────────────────────────────────────────────────
    llm_provider: str = Field(default="mock")
    llm_api_url: str = Field(default="")
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_model_name: str = Field(default="mock-model")

    # ── Embedding Provider ───────────────────────────────────────────────
    embedding_provider: str = Field(default="mock")
    embedding_api_url: str = Field(default="")
    embedding_api_key: SecretStr = Field(default=SecretStr(""))
    embedding_dimension: int = Field(default=1024)
    embedding_model_name: str = Field(default="mock-embedding")

    # ── Security ─────────────────────────────────────────────────────────
    field_encryption_key: SecretStr = Field(default=SecretStr("changeme-encryption-key"))
    max_upload_size_bytes: int = Field(default=50 * 1024 * 1024)  # 50 MB
    rate_limit_per_minute: int = Field(default=120)

    # ── Logging ──────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # ── Validators ───────────────────────────────────────────────────────

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            msg = "DATABASE_URL must use postgresql+asyncpg:// scheme"
            raise ValueError(msg)
        return v

    @field_validator("app_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            msg = f"LOG_LEVEL must be one of {allowed}"
            raise ValueError(msg)
        return upper

    @model_validator(mode="after")
    def validate_production_safety(self) -> Settings:
        """Prevent production from running with unsafe defaults."""
        if self.app_env.lower() != "production":
            return self

        _placeholder_re = re.compile(r"<secret>|changeme|placeholder|CHANGE_ME", re.IGNORECASE)

        # Check placeholder secrets
        secret_fields = {
            "database_url": self.database_url,
            "kafka_sasl_password": self.kafka_sasl_password.get_secret_value(),
            "minio_secret_key": self.minio_secret_key.get_secret_value(),
            "field_encryption_key": self.field_encryption_key.get_secret_value(),
        }
        for field_name, value in secret_fields.items():
            if _placeholder_re.search(value):
                msg = f"Production environment must not use placeholder value for {field_name}"
                raise ValueError(msg)

        # Check Redis URL for placeholder password
        if _placeholder_re.search(self.redis_url):
            msg = "Production environment must not use placeholder password in REDIS_URL"
            raise ValueError(msg)

        # Wildcard CORS
        if "*" in self.app_cors_origins:
            msg = "Production environment must not use wildcard CORS origins"
            raise ValueError(msg)

        # JWT issuer/audience must be set
        if not self.keycloak_issuer_url:
            msg = "Production environment requires KEYCLOAK_ISSUER_URL"
            raise ValueError(msg)

        if not self.oidc_expected_audience:
            msg = "Production environment requires OIDC_EXPECTED_AUDIENCE"
            raise ValueError(msg)

        # Prevent superuser database connection
        if "postgres:" in self.database_url.split("@")[0] if "@" in self.database_url else False:
            msg = "Production environment must not use 'postgres' superuser in DATABASE_URL"
            raise ValueError(msg)

        return self

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_testing(self) -> bool:
        return self.app_env.lower() == "testing"


def get_settings() -> Settings:
    """Factory function for settings singleton.

    Used by FastAPI dependency injection. The settings instance is
    cached by Pydantic Settings internally.
    """
    return Settings()
