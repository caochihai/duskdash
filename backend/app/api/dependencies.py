"""Request-scoped service composition and fail-closed RLS transactions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_principal
from app.auth.principal import CurrentPrincipal
from app.config import Settings
from app.db.rls_context import rls_transaction
from app.db.session import get_async_session
from app.exceptions import DependencyUnavailableError
from app.repositories.account_repository import AccountRepository
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.job_repository import JobRepository
from app.repositories.loan_repository import LoanRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.policy_repository import PolicyRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.agent_simulation_service import AgentSimulationService
from app.services.analysis_service import AnalysisService
from app.services.audit_service import AuditService
from app.services.conversation_service import (
    ConversationProcessingGuard,
    ConversationService,
)
from app.services.customer_assignment_service import CustomerAssignmentService
from app.services.customer_service import CustomerService
from app.services.document_service import DocumentService
from app.services.evidence_service import EvidenceService
from app.services.job_service import JobService
from app.services.loan_service import LoanService
from app.services.notification_service import NotificationService
from app.services.policy_service import PolicyService
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService
from app.services.upload_service import UploadService
from app.storage.interface import Storage

PrincipalDep = Annotated[CurrentPrincipal, Depends(get_current_principal)]


async def get_rls_session(
    principal: PrincipalDep,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AsyncIterator[AsyncSession]:
    """Set the three mandatory transaction-local RLS values for every query."""

    async with rls_transaction(
        session,
        employee_id=principal.employee_id,
        branch_id=principal.branch_id,
        is_admin=principal.is_admin,
    ):
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_rls_session)]


def get_settings_from_state(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise DependencyUnavailableError(
            "APPLICATION_NOT_READY", "Application settings are not initialized."
        )
    return settings


def get_storage(request: Request) -> Storage:
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise DependencyUnavailableError("MINIO_UNAVAILABLE", "Object storage is unavailable.")
    return cast(Storage, storage)


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditService(AuditRepository(session))


def get_customer_service(session: SessionDep) -> CustomerService:
    return CustomerService(
        CustomerRepository(session),
        AccountRepository(session),
        AuditService(AuditRepository(session)),
    )


def get_customer_assignment_service(
    request: Request, session: SessionDep
) -> CustomerAssignmentService:
    settings = get_settings_from_state(request)
    return CustomerAssignmentService(
        CustomerRepository(session),
        require_state_adapter(request, "redis"),
        AuditService(AuditRepository(session)),
        lease_ttl_seconds=settings.customer_assignment_lease_ttl_seconds,
    )


def get_conversation_service(request: Request, session: SessionDep) -> ConversationService:
    responder = getattr(request.app.state, "conversation_responder", None)
    processing_guard = None
    if responder is not None:
        settings = get_settings_from_state(request)
        audit = AuditService(AuditRepository(session))
        assignment = CustomerAssignmentService(
            CustomerRepository(session),
            require_state_adapter(request, "redis"),
            audit,
            lease_ttl_seconds=settings.customer_assignment_lease_ttl_seconds,
        )
        loan = LoanService(LoanRepository(session), audit, assignment)
        processing_guard = ConversationProcessingGuard(assignment, loan)
    return ConversationService(
        ConversationRepository(session),
        require_state_adapter(request, "context_router"),
        responder,
        processing_guard,
    )


def get_transaction_service(session: SessionDep) -> TransactionService:
    return TransactionService(
        TransactionRepository(session), AuditService(AuditRepository(session))
    )


def get_upload_service(request: Request, session: SessionDep) -> UploadService:
    settings = get_settings_from_state(request)
    return UploadService(
        DocumentRepository(session),
        get_storage(request),
        max_size_bytes=settings.max_upload_size_bytes,
        presigned_ttl_seconds=settings.minio_presigned_ttl_seconds,
        audit=AuditService(AuditRepository(session)),
    )


def get_document_service(request: Request, session: SessionDep) -> DocumentService:
    settings = get_settings_from_state(request)
    return DocumentService(
        DocumentRepository(session),
        get_storage(request),
        presigned_ttl_seconds=settings.minio_presigned_ttl_seconds,
        audit=AuditService(AuditRepository(session)),
    )


def get_loan_service(request: Request, session: SessionDep) -> LoanService:
    audit = AuditService(AuditRepository(session))
    settings = get_settings_from_state(request)
    assignment = CustomerAssignmentService(
        CustomerRepository(session),
        require_state_adapter(request, "redis"),
        audit,
        lease_ttl_seconds=settings.customer_assignment_lease_ttl_seconds,
    )
    return LoanService(LoanRepository(session), audit, assignment)


def get_analysis_service(session: SessionDep) -> AnalysisService:
    return AnalysisService(
        AnalysisRepository(session), AuditService(AuditRepository(session))
    )


def get_agent_simulation_service(request: Request) -> AgentSimulationService:
    """Expose synthetic design data only in non-production mock-provider mode."""

    settings = get_settings_from_state(request)
    if settings.is_production or settings.llm_provider.casefold() != "mock":
        raise DependencyUnavailableError(
            "AGENT_SIMULATION_DISABLED",
            "Synthetic agent simulation is available only in non-production mock mode.",
        )
    return AgentSimulationService()


def get_evidence_service(session: SessionDep) -> EvidenceService:
    return EvidenceService(
        EvidenceRepository(session), AuditService(AuditRepository(session))
    )


def get_policy_service(session: SessionDep) -> PolicyService:
    return PolicyService(PolicyRepository(session))


def get_report_service(request: Request, session: SessionDep) -> ReportService:
    settings = get_settings_from_state(request)
    return ReportService(
        ReportRepository(session),
        get_storage(request),
        presigned_ttl_seconds=settings.minio_presigned_ttl_seconds,
        audit=AuditService(AuditRepository(session)),
    )


def get_job_service(session: SessionDep) -> JobService:
    return JobService(JobRepository(session))


def get_notification_service(session: SessionDep) -> NotificationService:
    return NotificationService(NotificationRepository(session))


def require_state_adapter(request: Request, name: str) -> Any:
    adapter = getattr(request.app.state, name, None)
    if adapter is None:
        raise DependencyUnavailableError(
            "DEPENDENCY_UNAVAILABLE", f"Required adapter {name} is unavailable."
        )
    return adapter
