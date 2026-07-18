from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from app.document_processing.models import DocumentPipelineInput, DocumentPipelineResult, PipelineStep
from app.document_processing.pipeline import DocumentPipeline
from app.providers.embedding.mock import MockEmbeddingProvider
from app.providers.ocr.mock import MockOCRProvider
from app.storage.interface import Bucket, ObjectStat, PresignedRequest


class FakeStorage:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.original_exists = False
        self.copies: list[tuple[str, str, str, str]] = []
        self.puts: list[tuple[str, str, bytes, str]] = []

    async def create_presigned_put(self, *args: object, **kwargs: object) -> PresignedRequest:
        raise NotImplementedError

    async def create_presigned_get(self, *args: object, **kwargs: object) -> PresignedRequest:
        raise NotImplementedError

    async def stat_object(
        self, bucket: str, key: str, *, version_id: str | None = None
    ) -> ObjectStat:
        return ObjectStat(
            bucket=str(bucket),
            key=key,
            size_bytes=len(self.content),
            etag="etag",
            content_type="application/pdf",
            version_id=None,
            checksum_sha256_base64=None,
            metadata={},
        )

    async def object_exists(
        self, bucket: str, key: str, *, version_id: str | None = None
    ) -> bool:
        return self.original_exists

    async def get_object(
        self, bucket: str, key: str, *, version_id: str | None = None
    ) -> bytes:
        return self.content

    async def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> ObjectStat:
        self.puts.append((str(bucket), key, data, content_type))
        return await self.stat_object(str(bucket), key)

    async def copy_object(
        self, source_bucket: str, source_key: str, target_bucket: str, target_key: str
    ) -> ObjectStat:
        self.copies.append((str(source_bucket), source_key, str(target_bucket), target_key))
        self.original_exists = True
        return await self.stat_object(str(target_bucket), target_key)

    async def put_object_tags(self, bucket: str, key: str, tags: dict[str, str]) -> None:
        return None

    async def remove_object(
        self, bucket: str, key: str, *, version_id: str | None = None
    ) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class FakeSink:
    def __init__(self) -> None:
        self.results: list[DocumentPipelineResult] = []
        self.preserve_flags: list[bool] = []

    async def persist_result(
        self,
        job_id: object,
        result: DocumentPipelineResult,
        *,
        preserve_verified_fields: bool,
    ) -> None:
        self.results.append(result)
        self.preserve_flags.append(preserve_verified_fields)


class FakeProgress:
    def __init__(self) -> None:
        self.completed: list[PipelineStep] = []

    async def step_started(self, job_id: object, step: PipelineStep, progress_percent: int) -> None:
        return None

    async def step_completed(self, job_id: object, step: PipelineStep, progress_percent: int) -> None:
        self.completed.append(step)

    async def step_failed(self, job_id: object, step: PipelineStep, error_code: str) -> None:
        raise AssertionError(f"unexpected failed step {step}: {error_code}")


@pytest.mark.asyncio
async def test_document_pipeline_is_deterministic_and_original_copy_is_idempotent() -> None:
    content = b"SALARY payslip\nMonthly income: 28000000"
    storage = FakeStorage(content)
    sink = FakeSink()
    progress = FakeProgress()
    pipeline = DocumentPipeline(
        storage=storage,  # type: ignore[arg-type]
        ocr_provider=MockOCRProvider(),
        embedding_provider=MockEmbeddingProvider(),
        sink=sink,
        progress=progress,
    )
    upload_id = uuid4()
    request = DocumentPipelineInput(
        job_id=uuid4(),
        correlation_id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        source_key=f"uploads/{upload_id}/incoming",
        mime_type="application/pdf",
        expected_size_bytes=len(content),
        expected_sha256=hashlib.sha256(content).hexdigest(),
    )
    result = await pipeline.run(request)
    assert result.processing_status == "READY"
    assert result.classification == "SALARY_SLIP"
    assert result.fields[0].normalized_value_text == "28000000.0000"
    assert len(result.chunks[0].embedding or ()) == 1024
    assert len(storage.copies) == 1
    assert storage.puts[0][0] == Bucket.CUSTOMER_DOC_DERIVED
    assert sink.preserve_flags == [True]
    assert progress.completed == list(PipelineStep)

    await pipeline.run(request)
    assert len(storage.copies) == 1
    assert len(sink.results) == 2


@pytest.mark.asyncio
async def test_pipeline_rejects_checksum_mismatch_before_persistence() -> None:
    content = b"document"
    pipeline = DocumentPipeline(
        storage=FakeStorage(content),  # type: ignore[arg-type]
        ocr_provider=MockOCRProvider(),
        embedding_provider=MockEmbeddingProvider(),
        sink=FakeSink(),
    )
    request = DocumentPipelineInput(
        job_id=uuid4(),
        correlation_id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        source_key=f"uploads/{uuid4()}/incoming",
        mime_type="application/pdf",
        expected_size_bytes=len(content),
        expected_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="checksum"):
        await pipeline.run(request)
