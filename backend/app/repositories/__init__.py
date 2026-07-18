"""Repository interfaces used by application services and workers."""

from app.repositories.account_repository import AccountRepository
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.calculation_repository import CalculationRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.identity_repository import IdentityRepository
from app.repositories.inbox_repository import InboxRepository
from app.repositories.job_repository import JobRepository
from app.repositories.loan_repository import LoanRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.policy_repository import PolicyRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.transaction_repository import TransactionRepository

__all__ = [
    "AccountRepository",
    "AnalysisRepository",
    "AuditRepository",
    "CalculationRepository",
    "ConversationRepository",
    "CustomerRepository",
    "DocumentRepository",
    "EvidenceRepository",
    "IdempotencyRepository",
    "IdentityRepository",
    "InboxRepository",
    "JobRepository",
    "LoanRepository",
    "NotificationRepository",
    "OutboxRepository",
    "PolicyRepository",
    "ReportRepository",
    "TransactionRepository",
]
