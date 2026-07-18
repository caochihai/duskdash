from datetime import date
from typing import Any
from uuid import UUID, uuid4

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.policy_repository import PolicyRepository


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self.rows)


class FakeSession:
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any]) -> FakeResult:
        self.calls.append((str(statement), params))
        return FakeResult(self.responses.pop(0))


async def test_outbox_claim_is_filtered_by_payload_producer() -> None:
    session = FakeSession([[{"id": UUID("81000000-0000-4000-8000-000000000001")}]])
    repository = OutboxRepository(session)  # type: ignore[arg-type]
    rows = await repository.claim_pending_for_producer("bank-api", 25, "publisher-1")
    assert len(rows) == 1
    sql, params = session.calls[0]
    assert "payload ->> 'producer' = :producer" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert params["producer"] == "bank-api"
    assert params["locked_by"] == "publisher-1"


async def test_outbox_failure_applies_backoff_and_terminal_attempt_limit() -> None:
    event_id = UUID("81000000-0000-4000-8000-000000000001")
    session = FakeSession([[{"id": event_id, "status": "PENDING", "attempt_count": 1}]])
    repository = OutboxRepository(session)  # type: ignore[arg-type]
    row = await repository.mark_failed(event_id, "publisher-1", "safe failure", 30, max_attempts=5)
    assert row is not None
    sql, params = session.calls[0]
    assert "attempt_count = attempt_count + 1" in sql
    assert "make_interval(secs => :backoff_seconds)" in sql
    assert params["max_attempts"] == 5


async def test_policy_effective_version_has_inclusive_date_bounds() -> None:
    policy_id = UUID("43000000-0000-4000-8000-000000000001")
    session = FakeSession([[{"id": UUID("43100000-0000-4000-8000-000000000001")}]])
    repository = PolicyRepository(session)  # type: ignore[arg-type]
    row = await repository.effective_version(policy_id, date(2026, 7, 18))
    assert row is not None
    sql, params = session.calls[0]
    assert "effective_from <= :effective_on" in sql
    assert "effective_until >= :effective_on" in sql
    assert params["effective_on"] == date(2026, 7, 18)


async def test_customer_list_casts_optional_search_parameters_for_asyncpg() -> None:
    session = FakeSession([[]])
    repository = CustomerRepository(session)  # type: ignore[arg-type]

    rows, total = await repository.list(search=None)

    assert rows == []
    assert total == 0
    sql, params = session.calls[0]
    assert "CAST(:term AS TEXT) IS NULL" in sql
    assert "ILIKE CAST(:pattern AS TEXT)" in sql
    assert params["term"] is None


async def test_message_insert_casts_optional_parent_id_for_asyncpg() -> None:
    session = FakeSession([[]])
    repository = ConversationRepository(session)  # type: ignore[arg-type]

    row = await repository.add_message(
        uuid4(),
        employee_id=uuid4(),
        content="smoke",
        route={"route_type": "GENERAL", "complexity_level": 1},
    )

    assert row is None
    sql, params = session.calls[0]
    assert "CAST(:parent_message_id AS UUID) IS NULL" in sql
    assert "parent.id = CAST(:parent_message_id AS UUID)" in sql
    assert params["parent_message_id"] is None
