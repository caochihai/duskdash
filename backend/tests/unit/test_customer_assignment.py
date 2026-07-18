from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from app.auth.principal import CurrentPrincipal
from app.exceptions import ConflictError
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerAssignmentLeaseResponse
from app.services.customer_assignment_service import CustomerAssignmentService


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, dict[str, object]]] = []
        self.eval_calls: list[tuple[object, ...]] = []

    async def set(self, key: str, value: object, **kwargs: object) -> bool:
        token = str(value)
        self.set_calls.append((key, token, kwargs))
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = token
        return True

    async def eval(self, *args: object) -> int:
        self.eval_calls.append(args)
        key = str(args[2])
        token = str(args[3])
        if self.values.get(key) != token:
            return 0
        if len(args) == 4:
            del self.values[key]
        return 1


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


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


class FakeAssignmentRepository:
    def __init__(
        self,
        customer_id: UUID,
        *,
        assigned_employee_id: UUID | None = None,
        assignment_version: int = 1,
    ) -> None:
        self.row: dict[str, Any] = {
            "customer_id": customer_id,
            "assigned_employee_id": assigned_employee_id,
            "assignment_version": assignment_version,
        }

    async def get_assignment(self, customer_id: UUID) -> dict[str, Any] | None:
        return dict(self.row) if customer_id == self.row["customer_id"] else None

    async def claim_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        expected_version: int,
    ) -> dict[str, Any] | None:
        if (
            customer_id != self.row["customer_id"]
            or expected_version != self.row["assignment_version"]
            or self.row["assigned_employee_id"] not in (None, employee_id)
        ):
            return None
        self.row["assigned_employee_id"] = employee_id
        self.row["assignment_version"] += 1
        return dict(self.row)

    async def takeover_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        expected_version: int,
    ) -> dict[str, Any] | None:
        if (
            customer_id != self.row["customer_id"]
            or expected_version != self.row["assignment_version"]
        ):
            return None
        previous = self.row["assigned_employee_id"]
        self.row["assigned_employee_id"] = employee_id
        self.row["assignment_version"] += 1
        return {**self.row, "previous_assigned_employee_id": previous}

    async def release_assignment(
        self,
        customer_id: UUID,
        *,
        employee_id: UUID,
        assignment_version: int,
    ) -> dict[str, Any] | None:
        if (
            customer_id != self.row["customer_id"]
            or employee_id != self.row["assigned_employee_id"]
            or assignment_version != self.row["assignment_version"]
        ):
            return None
        self.row["assigned_employee_id"] = None
        self.row["assignment_version"] += 1
        return dict(self.row)


class FakeAudit:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record(self, **values: Any) -> dict[str, Any]:
        self.records.append(values)
        return values


def principal(
    employee_id: UUID,
    *,
    roles: frozenset[str] = frozenset({"credit_officer"}),
    is_admin: bool = False,
) -> CurrentPrincipal:
    return CurrentPrincipal(
        employee_id=employee_id,
        subject=f"subject-{employee_id}",
        branch_id=uuid4(),
        roles=roles,
        permissions=frozenset({"customer:read"}),
        is_admin=is_admin,
    )


def service(
    repository: FakeAssignmentRepository,
    redis: FakeRedis,
    audit: FakeAudit,
) -> CustomerAssignmentService:
    return CustomerAssignmentService(
        repository,
        redis,  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
        lease_ttl_seconds=120,
    )


@pytest.mark.asyncio
async def test_repository_uses_atomic_owner_and_version_predicates() -> None:
    customer_id = uuid4()
    employee_id = uuid4()
    session = FakeSession(
        [
            [{"customer_id": customer_id, "assignment_version": 2}],
            [{"customer_id": customer_id, "assignment_version": 3}],
            [{"customer_id": customer_id, "assignment_version": 4}],
        ]
    )
    repository = CustomerRepository(session)  # type: ignore[arg-type]

    await repository.claim_assignment(
        customer_id,
        employee_id=employee_id,
        expected_version=1,
    )
    claim_sql, claim_params = session.calls[0]
    assert "version = :expected_version" in claim_sql
    assert "relationship_manager_id IS NULL" in claim_sql
    assert "relationship_manager_id = :employee_id" in claim_sql
    assert "version = version + 1" in claim_sql
    assert claim_params["expected_version"] == 1

    await repository.takeover_assignment(
        customer_id,
        employee_id=employee_id,
        expected_version=2,
    )
    takeover_sql, _ = session.calls[1]
    assert "FOR UPDATE" in takeover_sql
    assert "previous_assigned_employee_id" in takeover_sql
    assert "customer_record.version = :expected_version" in takeover_sql

    await repository.release_assignment(
        customer_id,
        employee_id=employee_id,
        assignment_version=3,
    )
    release_sql, release_params = session.calls[2]
    assert "relationship_manager_id = :employee_id" in release_sql
    assert "version = :assignment_version" in release_sql
    assert "relationship_manager_id = NULL" in release_sql
    assert release_params["assignment_version"] == 3


@pytest.mark.asyncio
async def test_claim_is_atomic_and_returns_an_opaque_versioned_lease() -> None:
    customer_id = uuid4()
    employee_id = uuid4()
    repository = FakeAssignmentRepository(customer_id)
    redis = FakeRedis()
    audit = FakeAudit()

    result = await service(repository, redis, audit).claim(
        principal(employee_id), customer_id, expected_version=1
    )

    assert repository.row["assigned_employee_id"] == employee_id
    assert repository.row["assignment_version"] == 2
    assert result["assignment_version"] == 2
    assert len(str(result["lease_token"])) >= 32
    assert redis.set_calls[0][0] == f"bank-ai:lock:customer-assignment:{customer_id}:v2"
    assert redis.set_calls[0][2] == {"nx": True, "px": 120_000}
    assert audit.records[0]["action"] == "CUSTOMER_ASSIGNMENT_CLAIMED"
    assert "lease_token" not in audit.records[0]["metadata"]

    response = CustomerAssignmentLeaseResponse.model_validate(result)
    assert "lease_token" not in repr(response)
    assert response.model_dump()["lease_token"] == result["lease_token"]


@pytest.mark.asyncio
async def test_claim_conflicts_for_another_employee_but_allows_same_employee() -> None:
    customer_id = uuid4()
    owner_id = uuid4()
    repository = FakeAssignmentRepository(
        customer_id,
        assigned_employee_id=owner_id,
        assignment_version=4,
    )
    redis = FakeRedis()
    audit = FakeAudit()
    assignment_service = service(repository, redis, audit)

    with pytest.raises(ConflictError) as conflict:
        await assignment_service.claim(principal(uuid4()), customer_id, expected_version=4)
    assert conflict.value.code == "CUSTOMER_ALREADY_ASSIGNED"
    assert repository.row["assignment_version"] == 4

    result = await assignment_service.claim(
        principal(owner_id), customer_id, expected_version=4
    )
    assert result["assigned_employee_id"] == owner_id
    assert result["assignment_version"] == 5


@pytest.mark.asyncio
async def test_heartbeat_requires_persistent_owner_version_and_redis_token() -> None:
    customer_id = uuid4()
    owner_id = uuid4()
    repository = FakeAssignmentRepository(customer_id)
    redis = FakeRedis()
    audit = FakeAudit()
    assignment_service = service(repository, redis, audit)
    claimed = await assignment_service.claim(
        principal(owner_id), customer_id, expected_version=1
    )

    heartbeat = await assignment_service.heartbeat(
        principal(owner_id),
        customer_id,
        assignment_version=2,
        lease_token=str(claimed["lease_token"]),
    )
    assert heartbeat["lease_ttl_seconds"] == 120
    assert redis.eval_calls[-1][2:] == (
        f"bank-ai:lock:customer-assignment:{customer_id}:v2",
        claimed["lease_token"],
        "120000",
    )

    with pytest.raises(ConflictError) as wrong_token:
        await assignment_service.heartbeat(
            principal(owner_id),
            customer_id,
            assignment_version=2,
            lease_token="x" * 43,
        )
    assert wrong_token.value.code == "CUSTOMER_LEASE_NOT_OWNED"

    with pytest.raises(ConflictError) as wrong_employee:
        await assignment_service.heartbeat(
            principal(uuid4()),
            customer_id,
            assignment_version=2,
            lease_token=str(claimed["lease_token"]),
        )
    assert wrong_employee.value.code == "CUSTOMER_ALREADY_ASSIGNED"


@pytest.mark.asyncio
async def test_release_requires_both_persistent_owner_and_lease_owner() -> None:
    customer_id = uuid4()
    owner_id = uuid4()
    repository = FakeAssignmentRepository(customer_id)
    redis = FakeRedis()
    audit = FakeAudit()
    assignment_service = service(repository, redis, audit)
    claimed = await assignment_service.claim(
        principal(owner_id), customer_id, expected_version=1
    )

    with pytest.raises(ConflictError):
        await assignment_service.release(
            principal(uuid4()),
            customer_id,
            assignment_version=2,
            lease_token=str(claimed["lease_token"]),
        )
    assert repository.row["assigned_employee_id"] == owner_id

    with pytest.raises(ConflictError) as wrong_token:
        await assignment_service.release(
            principal(owner_id),
            customer_id,
            assignment_version=2,
            lease_token="x" * 43,
        )
    assert wrong_token.value.code == "CUSTOMER_LEASE_NOT_OWNED"
    assert repository.row["assigned_employee_id"] == owner_id

    released = await assignment_service.release(
        principal(owner_id),
        customer_id,
        assignment_version=2,
        lease_token=str(claimed["lease_token"]),
    )
    assert released["released"] is True
    assert released["assignment_version"] == 3
    assert repository.row["assigned_employee_id"] is None
    assert audit.records[-1]["action"] == "CUSTOMER_ASSIGNMENT_RELEASED"


@pytest.mark.asyncio
async def test_takeover_requires_manager_or_admin_and_is_audited() -> None:
    customer_id = uuid4()
    old_owner_id = uuid4()
    repository = FakeAssignmentRepository(
        customer_id,
        assigned_employee_id=old_owner_id,
        assignment_version=8,
    )
    redis = FakeRedis()
    audit = FakeAudit()
    assignment_service = service(repository, redis, audit)

    with pytest.raises(PermissionError):
        await assignment_service.takeover(
            principal(uuid4()),
            customer_id,
            expected_version=8,
            reason="Workload reassignment",
        )

    manager_id = uuid4()
    result = await assignment_service.takeover(
        principal(manager_id, roles=frozenset({"credit_manager"})),
        customer_id,
        expected_version=8,
        reason="Workload reassignment",
    )
    assert result["assigned_employee_id"] == manager_id
    assert result["assignment_version"] == 9
    record = audit.records[-1]
    assert record["action"] == "CUSTOMER_ASSIGNMENT_TAKEN_OVER"
    assert record["metadata"]["previous_assigned_employee_id"] == old_owner_id
    assert record["metadata"]["reason"] == "Workload reassignment"
    assert "lease_token" not in record["metadata"]


@pytest.mark.asyncio
async def test_assert_can_process_uses_postgres_authority_and_optionally_checks_lease() -> None:
    customer_id = uuid4()
    owner_id = uuid4()
    repository = FakeAssignmentRepository(customer_id)
    redis = FakeRedis()
    audit = FakeAudit()
    assignment_service = service(repository, redis, audit)
    claimed = await assignment_service.claim(
        principal(owner_id), customer_id, expected_version=1
    )

    state = await assignment_service.assert_can_process(principal(owner_id), customer_id)
    assert state["assigned_employee_id"] == owner_id
    await assignment_service.assert_can_process(
        principal(owner_id),
        customer_id,
        lease_token=str(claimed["lease_token"]),
    )

    with pytest.raises(ConflictError):
        await assignment_service.assert_can_process(principal(uuid4()), customer_id)
