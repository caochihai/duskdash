"""Human-controlled loan application and decision workflow."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from app.services.access import require_permission, require_role
from app.services.audit_service import AuditService
from app.services.protocols import PrincipalLike
from app.services.state_machine import LOAN_TRANSITIONS, require_transition


class LoanRepositoryLike(Protocol):
    async def create(self, values: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def get(self, loan_application_id: UUID) -> Mapping[str, Any] | None: ...

    async def update(
        self, loan_application_id: UUID, *, values: Mapping[str, Any], expected_version: int
    ) -> Mapping[str, Any] | None: ...

    async def add_party(
        self, loan_application_id: UUID, *, party_id: UUID, party_role: str
    ) -> Mapping[str, Any]: ...

    async def link_document(
        self, loan_application_id: UUID, *, document_id: UUID
    ) -> Mapping[str, Any]: ...

    async def checklist(self, loan_application_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def calculations(self, loan_application_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def policy_checks(self, loan_application_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def list_analyses(self, loan_application_id: UUID) -> Sequence[Mapping[str, Any]]: ...

    async def submit(
        self, loan_application_id: UUID, *, actor_id: UUID, expected_version: int
    ) -> Mapping[str, Any] | None: ...

    async def create_decision(
        self,
        loan_application_id: UUID,
        *,
        decision_type: str,
        approved_amount: Decimal | None,
        approved_term_months: int | None,
        conditions: Sequence[Mapping[str, Any]],
        rationale: str,
        decision_maker_id: UUID,
        approval_request_id: UUID | None,
        is_override: bool,
        override_reason: str | None,
    ) -> Mapping[str, Any]: ...


class CustomerAssignmentGuardLike(Protocol):
    async def assert_can_process(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        lease_token: str | None = None,
    ) -> Mapping[str, Any]: ...


_PARTY_ROLES = frozenset(
    {
        "PRIMARY_BORROWER",
        "CO_BORROWER",
        "GUARANTOR",
        "SPOUSE",
        "COLLATERAL_OWNER",
        "LEGAL_REPRESENTATIVE",
    }
)
_DECISION_TYPES = frozenset({"APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"})


class LoanService:
    def __init__(
        self,
        repository: LoanRepositoryLike,
        audit: AuditService | None = None,
        customer_assignment: CustomerAssignmentGuardLike | None = None,
    ) -> None:
        self._repository = repository
        self._audit = audit
        self._customer_assignment = customer_assignment

    async def create(
        self, principal: PrincipalLike, values: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:create")
        amount = Decimal(str(values["requested_amount"]))
        term = int(values["requested_term_months"])
        if amount <= 0 or term <= 0:
            raise ValueError("requested_amount and requested_term_months must be positive")
        if str(values.get("currency", "")) != "VND" and len(str(values.get("currency", ""))) != 3:
            raise ValueError("currency must be an ISO-4217 three-letter code")
        if self._customer_assignment is not None:
            await self._customer_assignment.assert_can_process(
                principal,
                UUID(str(values["primary_customer_id"])),
            )
        return await self._repository.create(
            {
                **values,
                "created_by": principal.employee_id,
                # A new application is owned by the employee who starts it.
                # Managers may explicitly reassign it through the guarded
                # update flow, but ordinary officers cannot create unowned
                # work that another officer can accidentally process.
                "assigned_employee_id": principal.employee_id,
            }
        )

    async def get(self, principal: PrincipalLike, loan_application_id: UUID) -> Mapping[str, Any]:
        require_permission(principal, "loan:read")
        row = await self._repository.get(loan_application_id)
        if row is None:
            raise LookupError("Loan application was not found or is outside the authorized scope")
        return row

    async def update(
        self,
        principal: PrincipalLike,
        loan_application_id: UUID,
        values: Mapping[str, Any],
        *,
        expected_version: int,
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:update")
        current = await self.get(principal, loan_application_id)
        _require_assigned_handler(principal, current)
        requested_assignee = values.get("assigned_employee_id")
        if requested_assignee is not None:
            assignee_id = UUID(str(requested_assignee))
            if assignee_id != principal.employee_id and not _can_reassign(principal):
                raise PermissionError("Only a credit manager can reassign a loan application")
        if "status" in values:
            require_transition(str(current["status"]), str(values["status"]), LOAN_TRANSITIONS)
            if str(values["status"]) in {"APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"}:
                raise PermissionError("Final loan status can only be set by the human decision endpoint")
        row = await self._repository.update(
            loan_application_id,
            values={**values, "updated_by": principal.employee_id},
            expected_version=expected_version,
        )
        if row is None:
            raise RuntimeError("Optimistic locking conflict")
        return row

    async def add_party(
        self,
        principal: PrincipalLike,
        loan_application_id: UUID,
        *,
        party_id: UUID,
        party_role: str,
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:update")
        _require_assigned_handler(
            principal, await self.get(principal, loan_application_id)
        )
        if party_role not in _PARTY_ROLES:
            raise ValueError(f"party_role must be one of {sorted(_PARTY_ROLES)}")
        return await self._repository.add_party(
            loan_application_id, party_id=party_id, party_role=party_role
        )

    async def link_document(
        self, principal: PrincipalLike, loan_application_id: UUID, document_id: UUID
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:update")
        _require_assigned_handler(
            principal, await self.get(principal, loan_application_id)
        )
        return await self._repository.link_document(loan_application_id, document_id=document_id)

    async def require_assigned_handler(
        self, principal: PrincipalLike, loan_application_id: UUID
    ) -> Mapping[str, Any]:
        """Return the loan only when this employee owns its processing work."""

        current = await self.get(principal, loan_application_id)
        _require_assigned_handler(principal, current)
        return current

    async def checklist(
        self, principal: PrincipalLike, loan_application_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "loan:read")
        return await self._repository.checklist(loan_application_id)

    async def calculations(
        self, principal: PrincipalLike, loan_application_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "loan:read")
        return await self._repository.calculations(loan_application_id)

    async def policy_checks(
        self, principal: PrincipalLike, loan_application_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "loan:read")
        return await self._repository.policy_checks(loan_application_id)

    async def analyses(
        self, principal: PrincipalLike, loan_application_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        require_permission(principal, "loan:read")
        return await self._repository.list_analyses(loan_application_id)

    async def submit(
        self,
        principal: PrincipalLike,
        loan_application_id: UUID,
        *,
        expected_version: int,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:submit")
        current = await self.get(principal, loan_application_id)
        _require_assigned_handler(principal, current)
        require_transition(str(current["status"]), "SUBMITTED_FOR_APPROVAL", LOAN_TRANSITIONS)
        row = await self._repository.submit(
            loan_application_id, actor_id=principal.employee_id, expected_version=expected_version
        )
        if row is None:
            raise RuntimeError("Optimistic locking conflict")
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="LOAN_SUBMITTED",
                resource_type="LOAN_APPLICATION",
                resource_id=loan_application_id,
                loan_application_id=loan_application_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
            )
        return row

    async def decide(
        self,
        principal: PrincipalLike,
        loan_application_id: UUID,
        *,
        decision_type: str,
        approved_amount: Decimal | None,
        approved_term_months: int | None,
        conditions: Sequence[Mapping[str, Any]],
        rationale: str,
        approval_request_id: UUID | None,
        is_override: bool,
        override_reason: str | None,
        request_id: UUID | None = None,
    ) -> Mapping[str, Any]:
        require_permission(principal, "loan:approve")
        require_role(principal, "loan_approver")
        current = await self.get(principal, loan_application_id)
        if str(current["status"]) != "SUBMITTED_FOR_APPROVAL":
            raise ValueError("Loan application is not awaiting an authorized human decision")
        if decision_type not in _DECISION_TYPES:
            raise ValueError(f"decision_type must be one of {sorted(_DECISION_TYPES)}")
        if decision_type.startswith("APPROVED") and (
            approved_amount is None or approved_amount <= 0 or not approved_term_months
        ):
            raise ValueError("Approved decisions require a positive amount and term")
        if decision_type == "APPROVED_WITH_CONDITIONS" and not conditions:
            raise ValueError("APPROVED_WITH_CONDITIONS requires at least one condition")
        if not rationale.strip():
            raise ValueError("A human rationale is required")
        if is_override and not (override_reason or "").strip():
            raise ValueError("An override reason is required")
        row = await self._repository.create_decision(
            loan_application_id,
            decision_type=decision_type,
            approved_amount=approved_amount,
            approved_term_months=approved_term_months,
            conditions=list(conditions),
            rationale=rationale,
            decision_maker_id=principal.employee_id,
            approval_request_id=approval_request_id,
            is_override=is_override,
            override_reason=override_reason,
        )
        if self._audit is not None:
            await self._audit.record(
                principal=principal,
                action="LOAN_DECISION_CREATED",
                resource_type="LOAN_DECISION",
                resource_id=UUID(str(row["id"])),
                loan_application_id=loan_application_id,
                result="SUCCESS",
                request_id=request_id,
                correlation_id=request_id,
                metadata={"decision_type": decision_type, "is_override": is_override},
            )
        return row


def _can_reassign(principal: PrincipalLike) -> bool:
    return bool(
        getattr(principal, "is_admin", False)
        or set(getattr(principal, "roles", ())).intersection({"admin", "credit_manager"})
    )


def _require_assigned_handler(
    principal: PrincipalLike, loan: Mapping[str, Any]
) -> None:
    assigned = loan.get("assigned_employee_id")
    if assigned is None:
        return
    if UUID(str(assigned)) == principal.employee_id or _can_reassign(principal):
        return
    raise PermissionError("Loan application is being handled by another employee")
