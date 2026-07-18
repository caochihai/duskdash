"""Object-storage ports and the MinIO/S3 adapter."""

from app.storage.interface import (
    Bucket,
    ObjectKey,
    ObjectStat,
    PresignedRequest,
    Storage,
    StorageDeleteNotPermittedError,
)
from app.storage.minio_storage import Boto3MinioStorage

__all__ = [
    "Boto3MinioStorage",
    "Bucket",
    "ObjectKey",
    "ObjectStat",
    "PresignedRequest",
    "Storage",
    "StorageDeleteNotPermittedError",
]
