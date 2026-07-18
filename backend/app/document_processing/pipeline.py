"""End-to-end document pipeline with injected persistence and providers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Protocol, TypeVar

from app.document_processing.chunking import DocumentChunker
from app.document_processing.classification import DeterministicClassifier
from app.document_processing.embedding import ChunkEmbedder
from app.document_processing.extraction import DeterministicFieldExtractor
from app.document_processing.models import (
    DocumentPipelineInput,
    DocumentPipelineResult,
    PageResult,
    PipelineStep,
)
from app.document_processing.normalization import FieldNormalizer
from app.document_processing.ocr import OCRProcessor
from app.document_processing.security_scan import DeterministicSecurityScanner
from app.document_processing.validation import FieldValidator
from app.providers.embedding.base import EmbeddingProvider
from app.providers.ocr.base import OCRProvider
from app.storage.interface import Bucket, ObjectKey, Storage

ResultT = TypeVar("ResultT")
_UPLOAD_KEY = re.compile(r"^uploads/[0-9a-f-]{36}/incoming$")


class PipelineProgress(Protocol):
    async def step_started(self, job_id: object, step: PipelineStep, progress_percent: int) -> None: ...

    async def step_completed(self, job_id: object, step: PipelineStep, progress_percent: int) -> None: ...

    async def step_failed(self, job_id: object, step: PipelineStep, error_code: str) -> None: ...


class PipelineSink(Protocol):
    """Database transaction port implemented outside the pipeline package."""

    async def persist_result(
        self,
        job_id: object,
        result: DocumentPipelineResult,
        *,
        preserve_verified_fields: bool,
    ) -> None: ...


class NullPipelineProgress:
    async def step_started(self, job_id: object, step: PipelineStep, progress_percent: int) -> None:
        return None

    async def step_completed(self, job_id: object, step: PipelineStep, progress_percent: int) -> None:
        return None

    async def step_failed(self, job_id: object, step: PipelineStep, error_code: str) -> None:
        return None


class DocumentPipeline:
    """Deterministic orchestration; no router, SQL, or Kafka concerns leak in."""

    _PROGRESS = {
        PipelineStep.VALIDATE_UPLOAD: 5,
        PipelineStep.SECURITY_SCAN: 12,
        PipelineStep.PERSIST_ORIGINAL: 20,
        PipelineStep.OCR: 38,
        PipelineStep.CLASSIFICATION: 45,
        PipelineStep.FIELD_EXTRACTION: 55,
        PipelineStep.NORMALIZATION: 62,
        PipelineStep.FIELD_VALIDATION: 70,
        PipelineStep.PAGE_GENERATION: 76,
        PipelineStep.CHUNKING: 84,
        PipelineStep.EMBEDDING: 94,
        PipelineStep.MARK_READY: 100,
    }

    def __init__(
        self,
        *,
        storage: Storage,
        ocr_provider: OCRProvider,
        embedding_provider: EmbeddingProvider,
        sink: PipelineSink,
        progress: PipelineProgress | None = None,
        max_size_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self._storage = storage
        self._ocr = OCRProcessor(ocr_provider)
        self._embedder = ChunkEmbedder(embedding_provider)
        self._sink = sink
        self._progress = progress or NullPipelineProgress()
        self._scanner = DeterministicSecurityScanner(max_size_bytes=max_size_bytes)
        self._classifier = DeterministicClassifier()
        self._extractor = DeterministicFieldExtractor()
        self._normalizer = FieldNormalizer()
        self._validator = FieldValidator()
        self._chunker = DocumentChunker()

    async def run(self, request: DocumentPipelineInput) -> DocumentPipelineResult:
        if request.source_bucket != Bucket.UPLOAD_QUARANTINE:
            raise ValueError("document pipeline source must be upload-quarantine")
        if not _UPLOAD_KEY.fullmatch(request.source_key):
            raise ValueError("quarantine key does not match uploads/{upload_id}/incoming")

        content = await self._step(
            request,
            PipelineStep.VALIDATE_UPLOAD,
            lambda: self._validate_upload(request),
        )
        await self._step(
            request,
            PipelineStep.SECURITY_SCAN,
            lambda: self._scanner.scan(content, declared_mime_type=request.mime_type),
        )

        original_key = ObjectKey.original(request.document_id, request.document_version_id)
        await self._step(
            request,
            PipelineStep.PERSIST_ORIGINAL,
            lambda: self._persist_original(request, original_key, content),
        )
        ocr_result = await self._step(
            request,
            PipelineStep.OCR,
            lambda: self._ocr.process(content, mime_type=request.mime_type),
        )
        pages = tuple(
            PageResult(
                page_number=page.page_number,
                text_content=page.text,
                ocr_confidence=Decimal(str(page.confidence)),
                width=page.width,
                height=page.height,
            )
            for page in ocr_result.pages
        )
        classification = await self._step(
            request,
            PipelineStep.CLASSIFICATION,
            lambda: self._classifier.classify("\n".join(page.text_content for page in pages)),
        )
        fields = await self._step(
            request,
            PipelineStep.FIELD_EXTRACTION,
            lambda: self._extractor.extract(pages),
        )
        fields = await self._step(
            request,
            PipelineStep.NORMALIZATION,
            lambda: self._normalizer.normalize(fields),
        )
        issues = await self._step(
            request,
            PipelineStep.FIELD_VALIDATION,
            lambda: self._validator.validate(
                pages=pages, fields=fields, classification=classification
            ),
        )
        pages = await self._step(
            request,
            PipelineStep.PAGE_GENERATION,
            lambda: _return(pages),
        )
        chunks = await self._step(
            request,
            PipelineStep.CHUNKING,
            lambda: self._chunker.chunk(pages),
        )
        embedded_chunks, embedding_result = await self._step(
            request,
            PipelineStep.EMBEDDING,
            lambda: self._embedder.embed(chunks),
        )

        ocr_key = ObjectKey.ocr_result(request.document_id, request.document_version_id)
        await self._storage.put_object(
            Bucket.CUSTOMER_DOC_DERIVED,
            ocr_key,
            ocr_result.model_dump_json().encode(),
            content_type="application/json",
            metadata={
                "document-id": str(request.document_id),
                "document-version-id": str(request.document_version_id),
            },
        )
        status = "NEEDS_HUMAN_REVIEW" if issues else "READY"
        result = DocumentPipelineResult(
            document_id=request.document_id,
            document_version_id=request.document_version_id,
            original_bucket=Bucket.CUSTOMER_DOC_ORIGINAL,
            original_key=original_key,
            ocr_bucket=Bucket.CUSTOMER_DOC_DERIVED,
            ocr_key=ocr_key,
            classification=classification.document_type,
            classification_confidence=classification.confidence,
            processing_status=status,
            pages=pages,
            fields=fields,
            chunks=embedded_chunks,
            issues=issues,
            provider_versions={
                "ocr_provider": ocr_result.provider,
                "ocr_model": ocr_result.model_name,
                "ocr_model_version": ocr_result.model_version,
                "embedding_provider": embedding_result.provider,
                "embedding_model": embedding_result.model_name,
                "embedding_model_version": embedding_result.model_version,
            },
        )
        await self._step(
            request,
            PipelineStep.MARK_READY,
            lambda: self._persist_result(request, result),
        )
        return result

    async def _validate_upload(self, request: DocumentPipelineInput) -> bytes:
        content = await self._storage.get_object(request.source_bucket, request.source_key)
        if len(content) != request.expected_size_bytes:
            raise ValueError("uploaded object size does not match the upload session")
        digest = hashlib.sha256(content).hexdigest()
        if digest != request.expected_sha256:
            raise ValueError("uploaded object checksum does not match the upload session")
        return content

    async def _persist_original(
        self, request: DocumentPipelineInput, original_key: str, content: bytes
    ) -> None:
        bucket = Bucket.CUSTOMER_DOC_ORIGINAL
        if await self._storage.object_exists(bucket, original_key):
            existing = await self._storage.stat_object(bucket, original_key)
            if existing.size_bytes != len(content):
                raise ValueError("existing original object does not match this document version")
            return
        await self._storage.copy_object(
            request.source_bucket,
            request.source_key,
            bucket,
            original_key,
        )

    async def _persist_result(
        self, request: DocumentPipelineInput, result: DocumentPipelineResult
    ) -> None:
        await self._sink.persist_result(
            request.job_id,
            result,
            preserve_verified_fields=True,
        )

    async def _step(
        self,
        request: DocumentPipelineInput,
        step: PipelineStep,
        operation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        progress = self._PROGRESS[step]
        await self._progress.step_started(request.job_id, step, max(0, progress - 1))
        try:
            result = await operation()
        except Exception as exc:
            await self._progress.step_failed(request.job_id, step, _error_code(exc))
            raise
        await self._progress.step_completed(request.job_id, step, progress)
        return result


async def _return(value: ResultT) -> ResultT:
    return value


def _error_code(exc: Exception) -> str:
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", type(exc).__name__).upper()
    return name[:50]
