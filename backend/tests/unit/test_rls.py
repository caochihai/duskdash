from types import TracebackType
from typing import Any
from uuid import UUID

import pytest

from app.db.rls_context import rls_transaction, set_rls_context


class FakeTransaction:
    def __init__(self, session: "FakeSession") -> None:
        self.session = session

    async def __aenter__(self) -> None:
        self.session.active = True

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.session.active = False


class FakeSession:
    def __init__(self, active: bool = False) -> None:
        self.active = active
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def in_transaction(self) -> bool:
        return self.active

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self)

    async def execute(self, statement: Any, params: dict[str, Any]) -> None:
        self.calls.append((str(statement), params))


EMPLOYEE_ID = UUID("10000000-0000-4000-8000-000000000001")
BRANCH_ID = UUID("30000000-0000-4000-8000-000000000002")


async def test_rls_transaction_sets_all_values_locally() -> None:
    session = FakeSession()
    async with rls_transaction(session, EMPLOYEE_ID, BRANCH_ID, False):  # type: ignore[arg-type]
        assert session.active is True
        assert len(session.calls) == 1
        sql, params = session.calls[0]
        assert "set_config('app.employee_id'" in sql
        assert "set_config('app.branch_id'" in sql
        assert "set_config('app.is_admin'" in sql
        assert params == {
            "employee_id": str(EMPLOYEE_ID),
            "branch_id": str(BRANCH_ID),
            "is_admin": "false",
        }
    assert session.active is False


async def test_rls_transaction_rejects_ambiguous_nested_transaction() -> None:
    session = FakeSession(active=True)
    with pytest.raises(RuntimeError, match="without an active transaction"):
        async with rls_transaction(session, EMPLOYEE_ID, BRANCH_ID):  # type: ignore[arg-type]
            pass


async def test_rls_context_rejects_invalid_uuid_before_sql() -> None:
    session = FakeSession()
    with pytest.raises(ValueError):
        await set_rls_context(session, "not-a-uuid", BRANCH_ID)  # type: ignore[arg-type]
    assert session.calls == []

