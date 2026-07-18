from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.repositories.conversation_repository import ConversationRepository
from app.services.conversation_service import ConversationService


@dataclass(slots=True)
class Principal:
    employee_id: UUID
    branch_id: UUID
    roles: set[str]
    permissions: set[str]
    is_admin: bool = False


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, dict[str, Any]] = {}

    async def create(
        self,
        *,
        employee_id: UUID,
        active_customer_id: UUID | None,
        active_loan_application_id: UUID | None,
        title: str | None,
    ) -> dict[str, Any]:
        row = {
            "id": uuid4(),
            "employee_id": employee_id,
            "active_customer_id": active_customer_id,
            "active_loan_application_id": active_loan_application_id,
            "title": title,
            "status": "ACTIVE",
            "started_at": datetime.now(UTC),
            "ended_at": None,
        }
        self.rows[row["id"]] = row
        return row

    async def get(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> dict[str, Any] | None:
        row = self.rows.get(conversation_id)
        return row if row is not None and row["employee_id"] == employee_id else None

    async def list_for_employee(
        self,
        *,
        employee_id: UUID,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            row
            for row in self.rows.values()
            if row["employee_id"] == employee_id
            and (customer_id is None or row["active_customer_id"] == customer_id)
            and (
                loan_application_id is None
                or row["active_loan_application_id"] == loan_application_id
            )
            and (status is None or row["status"] == status)
        ]

    async def close(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> dict[str, Any] | None:
        row = await self.get(conversation_id, employee_id=employee_id)
        if row is None:
            return None
        row["status"] = "CLOSED"
        row["ended_at"] = datetime.now(UTC)
        return row

    async def update_title(
        self,
        conversation_id: UUID,
        *,
        employee_id: UUID,
        title: str,
    ) -> dict[str, Any] | None:
        row = await self.get(conversation_id, employee_id=employee_id)
        if row is None:
            return None
        row["title"] = title
        return row

    async def messages(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> list[dict[str, Any]]:
        del conversation_id, employee_id
        return []

    async def add_message(
        self,
        conversation_id: UUID,
        *,
        employee_id: UUID,
        content: str,
        route: dict[str, Any],
    ) -> dict[str, Any] | None:
        if await self.get(conversation_id, employee_id=employee_id) is None:
            return None
        return {
            "id": uuid4(),
            "conversation_id": conversation_id,
            "sender_type": "EMPLOYEE",
            "sender_id": employee_id,
            "content": content,
            "route": route,
        }


class AllowingContextRouter:
    async def authorize(
        self,
        *,
        employee_id: UUID,
        customer_id: UUID | None,
        loan_application_id: UUID | None,
        attachment_ids: tuple[UUID, ...] = (),
    ) -> tuple[frozenset[UUID], frozenset[UUID]]:
        del employee_id, attachment_ids
        customers = frozenset({customer_id}) if customer_id else frozenset()
        loans = frozenset({loan_application_id}) if loan_application_id else frozenset()
        return customers, loans

    async def route(
        self,
        *,
        employee_id: UUID,
        conversation: dict[str, Any],
        message: str,
        attachment_ids: list[UUID],
    ) -> dict[str, Any]:
        del employee_id, conversation, message, attachment_ids
        return {"route_type": "DIRECT", "complexity_level": 2}


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def first(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self._rows)


class RecordingSession:
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any]) -> FakeResult:
        self.calls.append((str(statement), params))
        return FakeResult(self._responses.pop(0))


def _principal(*, is_admin: bool = False) -> Principal:
    return Principal(
        employee_id=uuid4(),
        branch_id=uuid4(),
        roles={"admin"} if is_admin else {"relationship_manager"},
        permissions={"customer:read"},
        is_admin=is_admin,
    )


@pytest.mark.asyncio
async def test_two_employees_have_separate_conversations_for_same_customer() -> None:
    repository = InMemoryConversationRepository()
    service = ConversationService(repository, AllowingContextRouter())
    employee_a = _principal()
    employee_b = _principal()
    customer_id = uuid4()

    conversation_a = await service.create(
        employee_a,
        active_customer_id=customer_id,
        active_loan_application_id=None,
        title="Employee A review",
    )
    conversation_b = await service.create(
        employee_b,
        active_customer_id=customer_id,
        active_loan_application_id=None,
        title="Employee B review",
    )

    assert conversation_a["id"] != conversation_b["id"]
    assert [row["id"] for row in await service.list(employee_a, customer_id=customer_id)] == [
        conversation_a["id"]
    ]
    assert [row["id"] for row in await service.list(employee_b, customer_id=customer_id)] == [
        conversation_b["id"]
    ]

    with pytest.raises(LookupError, match="not found"):
        await service.get(employee_a, conversation_b["id"])


@pytest.mark.asyncio
async def test_admin_api_scope_does_not_override_conversation_ownership() -> None:
    repository = InMemoryConversationRepository()
    service = ConversationService(repository, AllowingContextRouter())
    owner = _principal()
    other_admin = _principal(is_admin=True)
    conversation = await service.create(
        owner,
        active_customer_id=uuid4(),
        active_loan_application_id=None,
        title="Owner private notes",
    )

    assert await service.list(other_admin) == []
    with pytest.raises(LookupError, match="not found"):
        await service.close(other_admin, conversation["id"])


@pytest.mark.asyncio
async def test_close_is_owner_scoped_idempotent_and_filterable() -> None:
    repository = InMemoryConversationRepository()
    service = ConversationService(repository, AllowingContextRouter())
    owner = _principal()
    loan_application_id = uuid4()
    conversation = await service.create(
        owner,
        active_customer_id=uuid4(),
        active_loan_application_id=loan_application_id,
        title="Repayment review",
    )

    closed = await service.close(owner, conversation["id"])
    closed_again = await service.close(owner, conversation["id"])

    assert closed["status"] == "CLOSED"
    assert closed_again["ended_at"] == closed["ended_at"]
    assert [
        row["id"]
        for row in await service.list(
            owner,
            loan_application_id=loan_application_id,
            status="closed",
        )
    ] == [conversation["id"]]


@pytest.mark.asyncio
async def test_update_title_is_trimmed_and_owner_scoped() -> None:
    repository = InMemoryConversationRepository()
    service = ConversationService(repository, AllowingContextRouter())
    owner = _principal()
    other = _principal()
    conversation = await service.create(
        owner,
        active_customer_id=None,
        active_loan_application_id=None,
        title="Initial title",
    )

    updated = await service.update_title(
        owner,
        conversation["id"],
        title="  Updated title  ",
    )

    assert updated["title"] == "Updated title"
    with pytest.raises(LookupError, match="not found"):
        await service.update_title(other, conversation["id"], title="Not allowed")


@pytest.mark.asyncio
async def test_repository_list_and_close_have_mandatory_owner_predicates() -> None:
    employee_id = uuid4()
    conversation_id = uuid4()
    session = RecordingSession([[], []])
    repository = ConversationRepository(session)  # type: ignore[arg-type]

    await repository.list_for_employee(employee_id=employee_id, customer_id=uuid4())
    await repository.close(conversation_id, employee_id=employee_id)

    list_sql, list_params = session.calls[0]
    close_sql, close_params = session.calls[1]
    assert "WHERE employee_id = :employee_id" in list_sql
    assert list_params["employee_id"] == employee_id
    assert "WHERE id = :conversation_id AND employee_id = :employee_id" in close_sql
    assert close_params["employee_id"] == employee_id
