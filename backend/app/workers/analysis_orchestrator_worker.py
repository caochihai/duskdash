"""Analysis-orchestrator handler and process entry point."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.orchestrator import AnalysisOrchestrator, AnalysisPlan
from app.messaging.event_envelope import EventEnvelope
from app.messaging.topic_registry import Topic
from app.workers.runtime import WorkerSpec, run_cli

SPEC = WorkerSpec(
    name="analysis-orchestrator",
    principal="analysis-orchestrator",
    group_id="analysis-orchestrator-group",
    topics=frozenset({Topic.ANALYSIS_COMMANDS, Topic.DOCUMENT_EVENTS}),
    handled_event_types=frozenset(
        {
            "analysis.requested",
            "analysis.document-agent.requested",
            "analysis.validation.requested",
            "analysis.synthesis.requested",
            "document.processing.completed",
            "document.processing.failed",
        }
    ),
)


class AnalysisPlanRepository(Protocol):
    async def persist_plan(self, event: EventEnvelope, plan: AnalysisPlan) -> None: ...


class AnalysisOrchestratorWorker:
    def __init__(self, repository: AnalysisPlanRepository, orchestrator: AnalysisOrchestrator) -> None:
        self._repository = repository
        self._orchestrator = orchestrator

    async def handle(self, event: EventEnvelope) -> UUID | None:
        if event.event_type != "analysis.requested":
            return None
        plan = self._orchestrator.create_plan(event.resource.id)
        await self._repository.persist_plan(event, plan)
        return event.resource.id


def main() -> None:
    run_cli("analysis_orchestrator_worker", SPEC)


if __name__ == "__main__":
    main()
