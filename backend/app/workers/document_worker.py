"""Document-worker handler and process entry point."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.document_processing.models import DocumentPipelineInput
from app.document_processing.pipeline import DocumentPipeline
from app.messaging.event_envelope import EventEnvelope
from app.messaging.topic_registry import Topic
from app.workers.runtime import WorkerSpec, run_cli

SPEC = WorkerSpec(
    name="document-worker",
    principal="document-worker",
    group_id="document-worker-group",
    topics=frozenset({Topic.DOCUMENT_COMMANDS}),
    handled_event_types=frozenset(
        {
            "document.processing.requested",
            "document.security-scan.requested",
            "document.ocr.requested",
            "document.classification.requested",
            "document.extraction.requested",
            "document.embedding.requested",
        }
    ),
)


class DocumentWorkRepository(Protocol):
    async def load_pipeline_input(self, event: EventEnvelope) -> DocumentPipelineInput: ...


class DocumentWorker:
    def __init__(self, repository: DocumentWorkRepository, pipeline: DocumentPipeline) -> None:
        self._repository = repository
        self._pipeline = pipeline

    async def handle(self, event: EventEnvelope) -> UUID | None:
        if event.event_type not in SPEC.handled_event_types:
            return None
        request = await self._repository.load_pipeline_input(event)
        result = await self._pipeline.run(request)
        return result.document_version_id


def main() -> None:
    run_cli("document_worker", SPEC)


if __name__ == "__main__":
    main()
