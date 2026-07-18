from __future__ import annotations

from uuid import uuid4

import pytest

from app.storage.interface import Bucket, ObjectKey, StorageDeleteNotPermittedError
from app.storage.minio_storage import Boto3MinioStorage


class FakeS3Client:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[str, object]] = []

    def generate_presigned_url(self, operation: str, **kwargs: object) -> str:
        self.calls.append((operation, kwargs))
        return f"http://{self.name}/{operation}"

    def head_object(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("head_object", kwargs))
        return {
            "ContentLength": 42,
            "ETag": '"etag-value"',
            "ContentType": "application/pdf",
            "ChecksumSHA256": "base64-checksum",
            "Metadata": {"document-id": "id"},
        }

    def close(self) -> None:
        self.calls.append(("close", None))


def make_storage() -> tuple[Boto3MinioStorage, FakeS3Client, FakeS3Client]:
    internal = FakeS3Client("minio:9000")
    public = FakeS3Client("localhost:9000")
    storage = Boto3MinioStorage(
        internal_endpoint="http://minio:9000",
        public_endpoint="http://localhost:9000",
        access_key="bank-api",
        secret_key="test-secret",
        internal_client=internal,
        public_client=public,
    )
    return storage, internal, public


def test_object_keys_match_infrastructure_contract() -> None:
    document_id = uuid4()
    version_id = uuid4()
    assert ObjectKey.original(document_id, version_id) == (
        f"documents/{document_id}/versions/{version_id}/original"
    )
    assert ObjectKey.page_image(document_id, version_id, 1).endswith("/pages/0001.png")
    assert ObjectKey.ocr_result(document_id, version_id).endswith("/ocr/result.json")
    with pytest.raises(ValueError):
        ObjectKey.page_image(document_id, version_id, 0)


@pytest.mark.asyncio
async def test_public_client_signs_and_internal_client_heads_with_checksum() -> None:
    storage, internal, public = make_storage()
    request = await storage.create_presigned_put(
        Bucket.UPLOAD_QUARANTINE,
        ObjectKey.upload(uuid4()),
        content_type="application/pdf",
        checksum_sha256_base64="expected-base64",
    )
    assert request.url.startswith("http://localhost:9000")
    assert request.headers["x-amz-checksum-sha256"] == "expected-base64"
    assert not internal.calls
    params = public.calls[0][1]["Params"]
    assert params["ChecksumSHA256"] == "expected-base64"

    stat = await storage.stat_object(Bucket.CUSTOMER_DOC_ORIGINAL, "documents/id")
    assert stat.checksum_sha256_base64 == "base64-checksum"
    assert stat.etag == "etag-value"
    assert internal.calls[-1][1]["ChecksumMode"] == "ENABLED"


@pytest.mark.asyncio
async def test_delete_is_rejected_before_calling_minio() -> None:
    storage, internal, _public = make_storage()
    with pytest.raises(StorageDeleteNotPermittedError):
        await storage.remove_object(Bucket.UPLOAD_QUARANTINE, "uploads/id/incoming")
    assert not internal.calls
