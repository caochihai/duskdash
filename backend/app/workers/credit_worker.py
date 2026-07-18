"""Credit expert worker; shares the analysis command topic via its own group."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.base import AgentInput, AgentOutput
from app.agents.credit_agent import CreditAgent
from app.messaging.event_envelope import EventEnvelope
from app.messaging.topic_registry import Topic
from app.workers.runtime import WorkerSpec, run_cli

SPEC = WorkerSpec(
    name="credit-worker",
    principal="credit-worker",
    group_id="credit-worker-group",
    topics=frozenset({Topic.ANALYSIS_COMMANDS}),
    handled_event_types=frozenset({"analysis.credit-agent.requested"}),
)


class CreditWorkRepository(Protocol):
    async def load_input(self, event: EventEnvelope) -> AgentInput: ...

    async def persist_output(self, event: EventEnvelope, output: AgentOutput) -> UUID: ...


class CreditWorker:
    def __init__(self, repository: CreditWorkRepository, agent: CreditAgent) -> None:
        self._repository = repository
        self._agent = agent

    async def handle(self, event: EventEnvelope) -> UUID | None:
        if event.event_type != "analysis.credit-agent.requested":
            return None
        request = await self._repository.load_input(event)
        output = await self._agent.run(request)
        return await self._repository.persist_output(event, output)


def main() -> None:
    run_cli("credit_worker", SPEC)


if __name__ == "__main__":
    main()
