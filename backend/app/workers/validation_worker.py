"""Logical validator executed under the analysis-orchestrator identity.

Infrastructure intentionally provisions no separate validation-worker SCRAM
principal or consumer group, so this handler must be assembled into the
analysis-orchestrator process rather than opening its own Kafka connection.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.base import AgentOutput
from app.agents.validator import EvidenceValidator, ValidationOutcome
from app.messaging.event_envelope import EventEnvelope
from app.workers.runtime import run_cli


class ValidationWorkRepository(Protocol):
    async def load_outputs(self, event: EventEnvelope) -> tuple[AgentOutput, ...]: ...

    async def authorized_sources(self, event: EventEnvelope) -> frozenset[UUID]: ...

    async def valid_calculations(self, event: EventEnvelope) -> frozenset[UUID]: ...

    async def valid_policy_clauses(self, event: EventEnvelope) -> frozenset[UUID]: ...

    async def persist_validation(
        self, event: EventEnvelope, outcome: ValidationOutcome
    ) -> UUID: ...


class ValidationWorker:
    def __init__(self, repository: ValidationWorkRepository, validator: EvidenceValidator) -> None:
        self._repository = repository
        self._validator = validator

    async def handle(self, event: EventEnvelope) -> UUID | None:
        if event.event_type != "analysis.validation.requested":
            return None
        outcome = await self._validator.validate(
            await self._repository.load_outputs(event),
            authorized_source_ids=await self._repository.authorized_sources(event),
            valid_calculation_ids=await self._repository.valid_calculations(event),
            valid_policy_clause_ids=await self._repository.valid_policy_clauses(event),
        )
        return await self._repository.persist_validation(event, outcome)


def main() -> None:
    run_cli("validation_worker")


if __name__ == "__main__":
    main()
