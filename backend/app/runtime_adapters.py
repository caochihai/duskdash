"""Concrete API runtime wiring for the infrastructure-owned services."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import httpx
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text

from app.agents.context_router import ContextRouter, RoutingRequest
from app.auth.principal import EmployeeAccessRecord
from app.cache.pubsub import RedisPubSub
from app.config import Settings
from app.db import session as db_session
from app.db.rls_context import set_rls_context
from app.repositories.identity_repository import IdentityRepository
from app.providers.llm.openai_compat import OpenAICompatLLMProvider
from app.services.llm_conversation_responder import LLMConversationResponder
from app.services.mock_conversation_responder import MockConversationResponder
from app.storage.minio_storage import Boto3MinioStorage


class DatabasePrincipalResolver:
    """Resolve every JWT subject in its own concurrency-safe DB session."""

    async def resolve(self, subject: str) -> EmployeeAccessRecord | None:
        factory = db_session.AsyncSessionFactory
        if factory is None:
            return None
        async with factory() as session:
            return await IdentityRepository(session).resolve(subject)


class AuthorizedContextRouter:
    """Check PostgreSQL/RLS ownership before deterministic semantic routing."""

    def __init__(self) -> None:
        self._router = ContextRouter()

    async def authorize(
        self,
        *,
        employee_id: UUID,
        customer_id: UUID | None,
        loan_application_id: UUID | None,
        attachment_ids: tuple[UUID, ...] = (),
    ) -> tuple[frozenset[UUID], frozenset[UUID]]:
        factory = db_session.AsyncSessionFactory
        if factory is None:
            raise RuntimeError("Database is not initialized")
        async with factory() as session, session.begin():
            identity = (
                await session.execute(
                    text(
                        """
                        SELECT branch_id
                        FROM identity.employee
                        WHERE id = :employee_id AND employment_status = 'ACTIVE'
                        """
                    ),
                    {"employee_id": employee_id},
                )
            ).mappings().one_or_none()
            if identity is None:
                raise PermissionError("Employee is not active")
            await set_rls_context(session, employee_id, identity["branch_id"], False)

            customers: set[UUID] = set()
            if customer_id is not None:
                allowed = await session.scalar(
                    text(
                        "SELECT identity.can_access_customer(:employee_id, :customer_id)"
                    ),
                    {"employee_id": employee_id, "customer_id": customer_id},
                )
                if not allowed:
                    raise PermissionError("Customer context is outside the authorized scope")
                customers.add(customer_id)

            loans: set[UUID] = set()
            if loan_application_id is not None:
                allowed = await session.scalar(
                    text("SELECT identity.can_access_loan(:employee_id, :loan_id)"),
                    {"employee_id": employee_id, "loan_id": loan_application_id},
                )
                if not allowed:
                    raise PermissionError("Loan context is outside the authorized scope")
                loan_customer_id = await session.scalar(
                    text(
                        """
                        SELECT primary_customer_id
                        FROM credit.loan_application
                        WHERE id = :loan_id
                        """
                    ),
                    {"loan_id": loan_application_id},
                )
                if loan_customer_id is None:
                    raise PermissionError("Loan context is outside the authorized scope")
                if customer_id is not None and UUID(str(loan_customer_id)) != customer_id:
                    raise PermissionError(
                        "Active customer and loan application do not describe the same case"
                    )
                loans.add(loan_application_id)

            if attachment_ids:
                visible = (
                    await session.execute(
                        text(
                            """
                            SELECT d.id
                            FROM document.document AS d
                            WHERE d.id = ANY(CAST(:attachment_ids AS uuid[]))
                              AND (
                                  (
                                      CAST(:customer_id AS uuid) IS NOT NULL
                                      AND EXISTS (
                                          SELECT 1
                                          FROM document.document_link AS dl
                                          WHERE dl.document_id = d.id
                                            AND dl.entity_type = 'CUSTOMER'
                                            AND dl.entity_id = CAST(:customer_id AS uuid)
                                      )
                                  )
                                  OR (
                                      CAST(:loan_id AS uuid) IS NOT NULL
                                      AND EXISTS (
                                          SELECT 1
                                          FROM document.document_link AS dl
                                          WHERE dl.document_id = d.id
                                            AND dl.entity_type = 'LOAN_APPLICATION'
                                            AND dl.entity_id = CAST(:loan_id AS uuid)
                                      )
                                  )
                              )
                            """
                        ),
                        {
                            "attachment_ids": [str(value) for value in attachment_ids],
                            "customer_id": customer_id,
                            "loan_id": loan_application_id,
                        },
                    )
                ).scalars().all()
                if {UUID(str(value)) for value in visible} != set(attachment_ids):
                    raise PermissionError("An attachment is outside the authorized scope")
        return frozenset(customers), frozenset(loans)

    async def route(
        self,
        *,
        employee_id: UUID,
        conversation: Mapping[str, Any],
        message: str,
        attachment_ids: tuple[UUID, ...] | list[UUID],
    ) -> Mapping[str, Any]:
        customer_value = conversation.get("active_customer_id")
        loan_value = conversation.get("active_loan_application_id")
        customer_id = UUID(str(customer_value)) if customer_value else None
        loan_id = UUID(str(loan_value)) if loan_value else None
        attachments = tuple(attachment_ids)
        customers, loans = await self.authorize(
            employee_id=employee_id,
            customer_id=customer_id,
            loan_application_id=loan_id,
            attachment_ids=attachments,
        )
        decision = await self._router.route(
            RoutingRequest(
                employee_id=employee_id,
                message=message,
                active_customer_id=customer_id,
                active_loan_application_id=loan_id,
                attachment_ids=attachments,
                accessible_customer_ids=customers,
                accessible_loan_ids=loans,
            )
        )
        return decision.model_dump(mode="json")


class InfrastructureReadinessProbe:
    """Dependency probe that checks the application identities, not admin paths."""

    def __init__(
        self,
        settings: Settings,
        redis: Redis,
        storage: Boto3MinioStorage | None,
    ) -> None:
        self._settings = settings
        self._redis = redis
        self._storage = storage

    async def check(self) -> Mapping[str, str]:
        checks = {
            "postgres": self._postgres(),
            "kafka": self._kafka(),
            "redis": self._redis_check(),
            "minio": self._minio(),
            "keycloak": self._keycloak(),
        }
        results = await asyncio.gather(
            *(self._bounded(check) for check in checks.values()),
            return_exceptions=True,
        )
        states = {
            name: "up" if result is True else "down"
            for name, result in zip(checks, results, strict=True)
        }
        states["ocr"] = "mock" if self._settings.ocr_provider == "mock" else "up"
        states["llm"] = "mock" if self._settings.llm_provider == "mock" else "up"
        return states

    @staticmethod
    async def _bounded(check: Any) -> bool:
        try:
            return bool(await asyncio.wait_for(check, timeout=5.0))
        except Exception:
            return False

    async def _postgres(self) -> bool:
        factory = db_session.AsyncSessionFactory
        if factory is None:
            return False
        async with factory() as session:
            # This intentionally checks a table permission installed by V016,
            # not merely whether the TCP socket accepts connections.
            value = await session.scalar(
                text("SELECT count(*) >= 0 FROM identity.employee")
            )
            return bool(value)

    async def _redis_check(self) -> bool:
        return bool(await self._redis.ping())

    async def _minio(self) -> bool:
        return bool(self._storage and await self._storage.healthcheck())

    async def _keycloak(self) -> bool:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(self._settings.keycloak_jwks_internal_url)
            return response.status_code == 200 and isinstance(response.json().get("keys"), list)

    async def _kafka(self) -> bool:
        producer = AIOKafkaProducer(
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            client_id=f"{self._settings.kafka_client_id}-readiness",
            security_protocol=self._settings.kafka_security_protocol,
            sasl_mechanism=self._settings.kafka_sasl_mechanism,
            sasl_plain_username=self._settings.kafka_sasl_username,
            sasl_plain_password=self._settings.kafka_sasl_password.get_secret_value(),
            request_timeout_ms=3000,
        )
        try:
            await producer.start()
            return True
        finally:
            await producer.stop()


class DefaultRuntimeAdapters:
    """Initialize and close concrete API adapters without changing infra state."""

    async def start(self, application: object, settings: Settings) -> None:
        if not isinstance(application, FastAPI):
            raise TypeError("application must be a FastAPI instance")
        await db_session.init_db(settings)
        redis = Redis.from_url(
            settings.redis_url_value,
            socket_timeout=settings.redis_socket_timeout,
            decode_responses=False,
        )
        storage = None
        if settings.minio_access_key and settings.minio_secret_key is not None:
            storage = Boto3MinioStorage(
                internal_endpoint=settings.minio_internal_endpoint,
                public_endpoint=settings.minio_public_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key.get_secret_value(),
                secure=settings.minio_secure,
                presigned_ttl_seconds=settings.minio_presigned_ttl_seconds,
            )
        application.state.principal_resolver = DatabasePrincipalResolver()
        application.state.redis = redis
        application.state.redis_pubsub = RedisPubSub(redis)
        application.state.storage = storage
        application.state.context_router = AuthorizedContextRouter()
        provider_name = settings.llm_provider.casefold()
        if provider_name == "mock" and not settings.is_production:
            responder: object | None = MockConversationResponder()
        elif (
            provider_name != "mock"
            and settings.llm_api_url
            and settings.llm_api_key is not None
        ):
            responder = LLMConversationResponder(
                OpenAICompatLLMProvider(
                    provider=settings.llm_provider,
                    api_url=settings.llm_api_url,
                    api_key=settings.llm_api_key.get_secret_value(),
                    model_name=settings.llm_model_name,
                )
            )
        else:
            responder = None
        application.state.conversation_responder = responder
        application.state.readiness_probe = InfrastructureReadinessProbe(
            settings, redis, storage
        )

    async def stop(self, application: object) -> None:
        if isinstance(application, FastAPI):
            redis = getattr(application.state, "redis", None)
            if isinstance(redis, Redis):
                await redis.aclose()
        await db_session.close_db()
