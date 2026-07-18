"""Compliance expert worker; uses only approved policy references."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.base import AgentInput, AgentOutput
from app.agents.compliance_agent import ComplianceAgent
from app.messaging.event_envelope import EventEnvelope
from app.messaging.topic_registry import Topic
from app.workers.runtime import WorkerSpec, run_cli

SPEC = WorkerSpec(
    name="compliance-worker",
    principal="compliance-worker",
    group_id="compliance-worker-group",
    topics=frozenset({Topic.ANALYSIS_COMMANDS}),
    handled_event_types=frozenset({"analysis.compliance-agent.requested"}),
)


class ComplianceWorkRepository(Protocol):
    async def load_input(self, event: EventEnvelope) -> AgentInput: ...

    async def persist_output(self, event: EventEnvelope, output: AgentOutput) -> UUID: ...


class ComplianceWorker:
    def __init__(self, repository: ComplianceWorkRepository, agent: ComplianceAgent) -> None:
        self._repository = repository
        self._agent = agent

    async def handle(self, event: EventEnvelope) -> UUID | None:
        if event.event_type != "analysis.compliance-agent.requested":
            return None
        request = await self._repository.load_input(event)
        output = await self._agent.run(request)
        return await self._repository.persist_output(event, output)


def main() -> None:
    run_cli("compliance_worker", SPEC)


if __name__ == "__main__":
    main()
