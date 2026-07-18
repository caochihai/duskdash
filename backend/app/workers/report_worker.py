"""Structured report persistence/PDF-artifact worker entry point."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.base import AgentOutput
from app.agents.synthesizer import ReportSynthesizer, SynthesizedReport
from app.agents.validator import ValidationOutcome
from app.messaging.event_envelope import EventEnvelope
from app.messaging.topic_registry import Topic
from app.workers.runtime import WorkerSpec, run_cli

SPEC = WorkerSpec(
    name="report-worker",
    principal="report-worker",
    group_id="report-worker-group",
    topics=frozenset({Topic.REPORT_COMMANDS, Topic.ANALYSIS_EVENTS}),
    handled_event_types=frozenset(
        {"report.generation.requested", "report.pdf.requested", "analysis.completed"}
    ),
)


class ReportWorkRepository(Protocol):
    async def load_synthesis_inputs(
        self, event: EventEnvelope
    ) -> tuple[tuple[AgentOutput, ...], ValidationOutcome]: ...

    async def persist_report(self, event: EventEnvelope, report: SynthesizedReport) -> UUID: ...

    async def generate_pdf_artifact(self, event: EventEnvelope) -> UUID: ...


class ReportWorker:
    def __init__(self, repository: ReportWorkRepository, synthesizer: ReportSynthesizer) -> None:
        self._repository = repository
        self._synthesizer = synthesizer

    async def handle(self, event: EventEnvelope) -> UUID | None:
        if event.event_type == "report.pdf.requested":
            return await self._repository.generate_pdf_artifact(event)
        if event.event_type not in {"report.generation.requested", "analysis.completed"}:
            return None
        outputs, validation = await self._repository.load_synthesis_inputs(event)
        report = await self._synthesizer.synthesize(outputs, validation)
        return await self._repository.persist_report(event, report)


def main() -> None:
    run_cli("report_worker", SPEC)


if __name__ == "__main__":
    main()
