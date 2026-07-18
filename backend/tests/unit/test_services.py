from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.audit_service import sanitize_audit_metadata
from app.services.idempotency_service import (
    IdempotencyConflictError,
    IdempotencyService,
    StoredResponse,
    canonical_request_hash,
)
from app.services.loan_service import LoanService
from app.services.state_machine import LOAN_TRANSITIONS, can_transition, require_transition
from app.services.upload_service import validate_upload_request


@dataclass(slots=True)
class Principal:
    employee_id: UUID
    branch_id: UUID
    roles: set[str]
    permissions: set[str]
    is_admin: bool = False


class FakeIdempotencyRepository:
    def __init__(self) -> None:
        self.row: dict[str, Any] | None = None

    async def get(self, **_: Any) -> dict[str, Any] | None:
        return self.row

    async def create(self, **values: Any) -> dict[str, Any]:
        self.row = dict(values)
        return self.row


class FakeLoanRepository:
    def __init__(self) -> None:
        self.current = {
            "id": uuid4(),
            "status": "SUBMITTED_FOR_APPROVAL",
            "version": 2,
        }
        self.decision: dict[str, Any] | None = None

    async def get(self, _loan_id: UUID) -> dict[str, Any]:
        return self.current

    async def create_decision(self, _loan_id: UUID, **values: Any) -> dict[str, Any]:
        self.decision = {"id": uuid4(), **values}
        return self.decision


def test_loan_state_machine_denies_ai_shortcut_to_approval() -> None:
    assert can_transition("READY_FOR_REVIEW", "SUBMITTED_FOR_APPROVAL", LOAN_TRANSITIONS)
    assert not can_transition("READY_FOR_REVIEW", "APPROVED", LOAN_TRANSITIONS)
    with pytest.raises(ValueError, match="not allowed"):
        require_transition("DRAFT", "APPROVED", LOAN_TRANSITIONS)


def test_request_hash_is_canonical() -> None:
    assert canonical_request_hash({"b": 2, "a": 1}) == canonical_request_hash({"a": 1, "b": 2})


@pytest.mark.asyncio
async def test_idempotency_replays_same_request_and_rejects_changed_request() -> None:
    repository = FakeIdempotencyRepository()
    service = IdempotencyService(repository)
    actor_id = uuid4()
    key = uuid4()
    request = {"amount": "700000000.0000", "currency": "VND"}
    await service.remember(
        actor_id=actor_id,
        operation_name="loan.create",
        idempotency_key=key,
        request_payload=request,
        response=StoredResponse(201, {"id": str(uuid4())}, "LOAN_APPLICATION", uuid4()),
    )
    replay = await service.replay(
        actor_id=actor_id,
        operation_name="loan.create",
        idempotency_key=key,
        request_payload=request,
    )
    assert replay is not None
    assert replay.status_code == 201
    with pytest.raises(IdempotencyConflictError):
        await service.replay(
            actor_id=actor_id,
            operation_name="loan.create",
            idempotency_key=key,
            request_payload={"amount": "1.0000", "currency": "VND"},
        )


def test_audit_metadata_redacts_credentials_recursively() -> None:
    cleaned = sanitize_audit_metadata(
        {
            "status": "SUCCESS",
            "authorization": "Bearer secret-token",
            "nested": {"api_key": "real-key", "safe": "value"},
        }
    )
    assert cleaned["authorization"] == "[REDACTED]"
    assert cleaned["nested"]["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["safe"] == "value"


@pytest.mark.parametrize(
    ("filename", "mime", "size", "sha"),
    [
        ("../loan.pdf", "application/pdf", 10, "a" * 64),
        ("loan.exe", "application/octet-stream", 10, "a" * 64),
        ("loan.pdf", "application/pdf", 0, "a" * 64),
        ("loan.pdf", "application/pdf", 10, "not-a-checksum"),
    ],
)
def test_upload_validation_rejects_unsafe_input(
    filename: str, mime: str, size: int, sha: str
) -> None:
    with pytest.raises(ValueError):
        validate_upload_request(
            filename=filename,
            mime_type=mime,
            size_bytes=size,
            sha256=sha,
            max_size_bytes=100,
        )


@pytest.mark.asyncio
async def test_only_authorized_human_approver_can_create_decision() -> None:
    repository = FakeLoanRepository()
    service = LoanService(repository)  # type: ignore[arg-type]
    principal = Principal(
        employee_id=uuid4(),
        branch_id=uuid4(),
        roles={"loan_approver"},
        permissions={"loan:read", "loan:approve"},
    )
    result = await service.decide(
        principal,
        repository.current["id"],
        decision_type="APPROVED",
        approved_amount=Decimal("650000000.0000"),
        approved_term_months=60,
        conditions=[],
        rationale="Authorized human review completed.",
        approval_request_id=None,
        is_override=False,
        override_reason=None,
    )
    assert result["decision_maker_id"] == principal.employee_id
    assert result["decision_type"] == "APPROVED"


@pytest.mark.asyncio
async def test_service_account_without_human_role_cannot_decide() -> None:
    repository = FakeLoanRepository()
    service = LoanService(repository)  # type: ignore[arg-type]
    principal = Principal(
        employee_id=uuid4(),
        branch_id=uuid4(),
        roles=set(),
        permissions={"loan:read", "loan:approve"},
    )
    with pytest.raises(PermissionError, match="role"):
        await service.decide(
            principal,
            repository.current["id"],
            decision_type="REJECTED",
            approved_amount=None,
            approved_term_months=None,
            conditions=[],
            rationale="Human review required.",
            approval_request_id=None,
            is_override=False,
            override_reason=None,
        )
