from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.loan_service import LoanService


@dataclass(slots=True)
class Principal:
    employee_id: UUID
    branch_id: UUID
    roles: set[str]
    permissions: set[str]
    is_admin: bool = False


class LoanRepository:
    def __init__(self, *, assigned_employee_id: UUID | None = None) -> None:
        self.loan_id = uuid4()
        self.current: dict[str, Any] = {
            "id": self.loan_id,
            "status": "DRAFT",
            "version": 1,
            "assigned_employee_id": assigned_employee_id,
        }
        self.created: dict[str, Any] | None = None

    async def create(self, values: dict[str, Any]) -> dict[str, Any]:
        self.created = dict(values)
        return {"id": self.loan_id, "status": "DRAFT", "version": 1, **values}

    async def get(self, _loan_id: UUID) -> dict[str, Any]:
        return dict(self.current)

    async def update(
        self, _loan_id: UUID, *, values: dict[str, Any], expected_version: int
    ) -> dict[str, Any]:
        assert expected_version == self.current["version"]
        self.current.update(values)
        self.current["version"] += 1
        return dict(self.current)


class AssignmentGuard:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    async def assert_can_process(
        self,
        actor: Principal,
        customer_id: UUID,
        *,
        lease_token: str | None = None,
    ) -> dict[str, Any]:
        assert lease_token is None
        self.calls.append((actor.employee_id, customer_id))
        return {"customer_id": customer_id, "assigned_employee_id": actor.employee_id}


def principal(employee_id: UUID, *, manager: bool = False) -> Principal:
    return Principal(
        employee_id=employee_id,
        branch_id=uuid4(),
        roles={"credit_manager"} if manager else {"credit_officer"},
        permissions={"loan:create", "loan:read", "loan:update", "loan:submit"},
    )


@pytest.mark.asyncio
async def test_new_loan_is_assigned_to_the_employee_who_created_it() -> None:
    employee_id = uuid4()
    repository = LoanRepository()
    service = LoanService(repository)  # type: ignore[arg-type]

    await service.create(
        principal(employee_id),
        {
            "primary_customer_id": uuid4(),
            "product_id": uuid4(),
            "requested_amount": "100000000.0000",
            "requested_term_months": 24,
            "currency": "VND",
            "loan_purpose": "WORKING_CAPITAL",
        },
    )

    assert repository.created is not None
    assert repository.created["assigned_employee_id"] == employee_id
    assert repository.created["created_by"] == employee_id


@pytest.mark.asyncio
async def test_new_loan_requires_the_persistent_customer_assignment() -> None:
    employee_id = uuid4()
    customer_id = uuid4()
    repository = LoanRepository()
    assignment = AssignmentGuard()
    service = LoanService(  # type: ignore[arg-type]
        repository,
        customer_assignment=assignment,
    )

    await service.create(
        principal(employee_id),
        {
            "primary_customer_id": customer_id,
            "product_id": uuid4(),
            "requested_amount": "100000000.0000",
            "requested_term_months": 24,
            "currency": "VND",
            "loan_purpose": "WORKING_CAPITAL",
        },
    )

    assert assignment.calls == [(employee_id, customer_id)]


@pytest.mark.asyncio
async def test_another_officer_cannot_modify_an_assigned_loan() -> None:
    repository = LoanRepository(assigned_employee_id=uuid4())
    service = LoanService(repository)  # type: ignore[arg-type]

    with pytest.raises(PermissionError, match="another employee"):
        await service.update(
            principal(uuid4()),
            repository.loan_id,
            {"loan_purpose": "REFINANCE"},
            expected_version=1,
        )


@pytest.mark.asyncio
async def test_credit_manager_can_reassign_an_assigned_loan() -> None:
    repository = LoanRepository(assigned_employee_id=uuid4())
    service = LoanService(repository)  # type: ignore[arg-type]
    manager = principal(uuid4(), manager=True)
    new_owner = uuid4()

    updated = await service.update(
        manager,
        repository.loan_id,
        {"assigned_employee_id": new_owner},
        expected_version=1,
    )

    assert updated["assigned_employee_id"] == new_owner
