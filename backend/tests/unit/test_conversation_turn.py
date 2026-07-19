from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from app.compat import UTC
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import ConversationReply, ConversationTurnResponse
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
        self.conversations: dict[UUID, dict[str, Any]] = {}
        self.message_rows: list[dict[str, Any]] = []

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
        self.conversations[row["id"]] = row
        return row

    async def get(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> dict[str, Any] | None:
        row = self.conversations.get(conversation_id)
        return row if row is not None and row["employee_id"] == employee_id else None

    async def list_for_employee(
        self,
        *,
        employee_id: UUID,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        del customer_id, loan_application_id, status
        return [
            row for row in self.conversations.values() if row["employee_id"] == employee_id
        ]

    async def close(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> dict[str, Any] | None:
        row = await self.get(conversation_id, employee_id=employee_id)
        if row is not None:
            row["status"] = "CLOSED"
            row["ended_at"] = datetime.now(UTC)
        return row

    async def messages(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> list[dict[str, Any]]:
        if await self.get(conversation_id, employee_id=employee_id) is None:
            return []
        return [
            row for row in self.message_rows if row["conversation_id"] == conversation_id
        ]

    async def add_message(
        self,
        conversation_id: UUID,
        *,
        employee_id: UUID,
        content: str,
        route: dict[str, Any],
        sender_type: str = "EMPLOYEE",
        sender_id: UUID | None = None,
        parent_message_id: UUID | None = None,
        attachment_ids: list[UUID] | tuple[UUID, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if await self.get(conversation_id, employee_id=employee_id) is None:
            return None
        if parent_message_id is not None and not any(
            row["id"] == parent_message_id and row["conversation_id"] == conversation_id
            for row in self.message_rows
        ):
            return None
        row = {
            "id": uuid4(),
            "conversation_id": conversation_id,
            "sender_type": sender_type,
            "sender_id": employee_id if sender_type == "EMPLOYEE" else sender_id,
            "content": content,
            "created_at": datetime.now(UTC),
            "parent_message_id": parent_message_id,
            "route_type": route.get("route_type"),
            "complexity_level": route.get("complexity_level"),
            "analysis_case_id": route.get("analysis_case_id"),
            "attachment_ids": list(dict.fromkeys(attachment_ids)),
            "metadata": dict(metadata) if metadata else None,
        }
        self.message_rows.append(row)
        return row


class FixedRouter:
    def __init__(
        self,
        analysis_case_id: UUID | None = None,
        route_type: str = "ORCHESTRATED",
    ) -> None:
        self.analysis_case_id = analysis_case_id
        self.route_type = route_type

    async def authorize(
        self,
        *,
        employee_id: UUID,
        customer_id: UUID | None,
        loan_application_id: UUID | None,
        attachment_ids: tuple[UUID, ...] = (),
    ) -> tuple[frozenset[UUID], frozenset[UUID]]:
        del employee_id, attachment_ids
        return (
            frozenset({customer_id}) if customer_id else frozenset(),
            frozenset({loan_application_id}) if loan_application_id else frozenset(),
        )

    async def route(
        self,
        *,
        employee_id: UUID,
        conversation: dict[str, Any],
        message: str,
        attachment_ids: list[UUID],
    ) -> dict[str, Any]:
        del employee_id, conversation, message, attachment_ids
        route: dict[str, Any] = {
            "route_type": self.route_type,
            "complexity_level": 4 if self.route_type == "ORCHESTRATED" else 3,
            "intent": "ASSESS_REPAYMENT_CAPACITY",
        }
        if self.analysis_case_id is not None:
            route["analysis_case_id"] = self.analysis_case_id
        return route


class RecordingResponder:
    def __init__(self, reply: ConversationReply) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    async def respond(
        self,
        *,
        principal: Principal,
        conversation: dict[str, Any],
        message: str,
        route: dict[str, Any],
        attachment_ids: list[UUID] | tuple[UUID, ...],
    ) -> ConversationReply:
        self.calls.append(
            {
                "principal": principal,
                "conversation": conversation,
                "message": message,
                "route": route,
                "attachment_ids": attachment_ids,
            }
        )
        return self.reply


class RecordingProcessingGuard:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def assert_can_process(
        self,
        principal: Principal,
        *,
        customer_id: UUID,
        loan_application_id: UUID | None,
        lease_token: str | None,
    ) -> None:
        self.calls.append(
            {
                "principal": principal,
                "customer_id": customer_id,
                "loan_application_id": loan_application_id,
                "lease_token": lease_token,
            }
        )


def _principal(*, can_analyze: bool = False) -> Principal:
    permissions = {"customer:read"}
    if can_analyze:
        permissions.add("loan:analyze")
    return Principal(
        employee_id=uuid4(),
        branch_id=uuid4(),
        roles={"credit_officer"},
        permissions=permissions,
    )


async def _create_conversation(
    service: ConversationService, principal: Principal
) -> dict[str, Any]:
    return dict(
        await service.create(
            principal,
            active_customer_id=uuid4(),
            active_loan_application_id=uuid4(),
            title="Repayment assessment",
        )
    )


@pytest.mark.asyncio
async def test_responder_is_optional_and_preserves_existing_single_message_behavior() -> None:
    repository = InMemoryConversationRepository()
    service = ConversationService(repository, FixedRouter())
    principal = _principal()
    conversation = await _create_conversation(service, principal)

    result = await service.add_message(
        principal,
        conversation["id"],
        content="  Đánh giá khả năng trả nợ  ",
        attachment_ids=[],
    )

    assert result["sender_type"] == "EMPLOYEE"
    assert result["content"] == "Đánh giá khả năng trả nợ"
    assert "assistant_message" not in result
    assert len(repository.message_rows) == 1

    api_result = ConversationTurnResponse.model_validate(result)
    assert api_result.assistant_message is None
    assert api_result.reply is None


@pytest.mark.asyncio
async def test_responder_persists_parented_assistant_message_and_structured_reply() -> None:
    analysis_case_id = uuid4()
    repository = InMemoryConversationRepository()
    responder = RecordingResponder(
        ConversationReply(
            content="Hồ sơ cần được kiểm tra bởi ba chuyên gia trước khi tổng hợp.",
            analysis_case_id=analysis_case_id,
            metadata={
                "mode": "MOCK_MULTI_AGENT",
                "validation": {"status": "APPROVED"},
                "citations": [
                    {
                        "source_type": "CALCULATION",
                        "source_id": str(uuid4()),
                        "source_locator": "mock://calculation/dti",
                        "label": "DTI mock",
                    }
                ],
                "human_decision_required": True,
            },
        )
    )
    processing_guard = RecordingProcessingGuard()
    service = ConversationService(
        repository,
        FixedRouter(),
        responder,
        processing_guard,
    )
    principal = _principal(can_analyze=True)
    conversation = await _create_conversation(service, principal)

    result = await service.add_message(
        principal,
        conversation["id"],
        content="Phân tích khả năng trả nợ",
        attachment_ids=[uuid4()],
        assignment_lease_token="lease-token-owned-by-this-employee-123456",
    )

    employee_message = repository.message_rows[0]
    assistant_message = repository.message_rows[1]
    assert responder.calls[0]["message"] == "Phân tích khả năng trả nợ"
    assert responder.calls[0]["route"]["complexity_level"] == 4
    assert responder.calls[0]["attachment_ids"] == tuple(
        employee_message["attachment_ids"]
    )
    # Tin nhắn kèm hồ sơ đi đường đọc-tài-liệu của responder nên guard phân
    # công khách hàng KHÔNG chạy (guard chỉ áp cho phân tích sâu không kèm file).
    assert processing_guard.calls == []
    assert assistant_message["sender_type"] == "ASSISTANT"
    assert assistant_message["sender_id"] is None
    assert assistant_message["parent_message_id"] == employee_message["id"]
    assert assistant_message["analysis_case_id"] == analysis_case_id
    assert result["assistant_message"]["id"] == assistant_message["id"]
    assert result["reply"]["metadata"]["human_decision_required"] is True

    listed = await service.messages(principal, conversation["id"])
    assert [row["sender_type"] for row in listed] == ["EMPLOYEE", "ASSISTANT"]

    with pytest.raises(LookupError, match="not found"):
        await service.messages(_principal(), conversation["id"])


@pytest.mark.asyncio
async def test_orchestrated_responder_requires_loan_analyze_before_persistence() -> None:
    repository = InMemoryConversationRepository()
    responder = RecordingResponder(ConversationReply(content="Should not run"))
    guard = RecordingProcessingGuard()
    service = ConversationService(repository, FixedRouter(), responder, guard)
    principal = _principal(can_analyze=False)
    conversation = await _create_conversation(service, principal)

    with pytest.raises(PermissionError, match="loan:analyze"):
        await service.add_message(
            principal,
            conversation["id"],
            content="Assess repayment capacity",
            attachment_ids=[],
        )

    assert repository.message_rows == []
    assert responder.calls == []
    assert guard.calls == []


@pytest.mark.asyncio
async def test_single_expert_responder_has_the_same_analysis_permission_gate() -> None:
    repository = InMemoryConversationRepository()
    responder = RecordingResponder(ConversationReply(content="Should not run"))
    guard = RecordingProcessingGuard()
    service = ConversationService(
        repository,
        FixedRouter(route_type="SINGLE_AGENT"),
        responder,
        guard,
    )
    principal = _principal(can_analyze=False)
    conversation = await _create_conversation(service, principal)

    with pytest.raises(PermissionError, match="loan:analyze"):
        await service.add_message(
            principal,
            conversation["id"],
            content="Review the documents",
            attachment_ids=[],
        )

    assert repository.message_rows == []
    assert responder.calls == []
    assert guard.calls == []


@pytest.mark.asyncio
async def test_orchestrated_responder_fails_closed_without_processing_guard() -> None:
    repository = InMemoryConversationRepository()
    responder = RecordingResponder(ConversationReply(content="Should not run"))
    service = ConversationService(repository, FixedRouter(), responder)
    principal = _principal(can_analyze=True)
    conversation = await _create_conversation(service, principal)

    with pytest.raises(RuntimeError, match="ownership guard"):
        await service.add_message(
            principal,
            conversation["id"],
            content="Assess repayment capacity",
            attachment_ids=[],
        )

    assert repository.message_rows == []
    assert responder.calls == []


@pytest.mark.asyncio
async def test_closed_conversation_rejects_new_turn_before_routing_or_persistence() -> None:
    repository = InMemoryConversationRepository()
    service = ConversationService(repository, FixedRouter())
    principal = _principal()
    conversation = await _create_conversation(service, principal)
    await service.close(principal, conversation["id"])

    with pytest.raises(ValueError, match="closed conversation"):
        await service.add_message(
            principal,
            conversation["id"],
            content="Analyze this closed case",
            attachment_ids=[],
        )

    assert repository.message_rows == []


def test_reply_contract_rejects_private_chain_of_thought_metadata() -> None:
    with pytest.raises(ValidationError, match="Private model reasoning"):
        ConversationReply(
            content="Employee-facing conclusion",
            metadata={"validation": {"chain-of-thought": "private reasoning"}},
        )


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
    def __init__(self, responses: list[list[dict[str, Any]]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._responses = list(responses or [])

    async def execute(self, statement: Any, params: dict[str, Any]) -> FakeResult:
        self.calls.append((str(statement), params))
        rows = self._responses.pop(0) if self._responses else []
        return FakeResult(rows)


@pytest.mark.asyncio
async def test_assistant_insert_is_owner_scoped_and_parent_scoped() -> None:
    session = RecordingSession()
    repository = ConversationRepository(session)  # type: ignore[arg-type]
    employee_id = uuid4()
    parent_message_id = uuid4()

    await repository.add_message(
        uuid4(),
        employee_id=employee_id,
        content="Structured assistant conclusion",
        route={"route_type": "SINGLE_AGENT", "complexity_level": 3},
        sender_type="ASSISTANT",
        parent_message_id=parent_message_id,
    )

    sql, params = session.calls[0]
    assert "c.employee_id = :employee_id" in sql
    assert "parent.conversation_id = c.id" in sql
    assert params["employee_id"] == employee_id
    assert params["parent_message_id"] == parent_message_id
    assert params["sender_type"] == "ASSISTANT"


@pytest.mark.asyncio
async def test_attachment_selection_does_not_invent_an_infrastructure_link_type() -> None:
    message_id = uuid4()
    attachment_id = uuid4()
    session = RecordingSession(
        [[{"id": message_id}]]
    )
    repository = ConversationRepository(session)  # type: ignore[arg-type]
    employee_id = uuid4()

    row = await repository.add_message(
        uuid4(),
        employee_id=employee_id,
        content="Review the selected document",
        route={"route_type": "SINGLE_AGENT", "complexity_level": 3},
        attachment_ids=[attachment_id],
    )

    assert row is not None
    assert row["attachment_ids"] == [attachment_id]
    assert len(session.calls) == 1
    message_sql, message_params = session.calls[0]
    assert "c.employee_id = :employee_id" in message_sql
    assert "'MESSAGE'" not in message_sql
    assert "'CHAT_ATTACHMENT'" not in message_sql
    assert message_params["employee_id"] == employee_id


@pytest.mark.asyncio
async def test_message_listing_stays_within_the_existing_ai_message_contract() -> None:
    session = RecordingSession([[]])
    repository = ConversationRepository(session)  # type: ignore[arg-type]

    await repository.messages(uuid4(), employee_id=uuid4())

    sql, _params = session.calls[0]
    assert "document.document_link" not in sql
    assert "c.employee_id = :employee_id" in sql
