"""Async wrapper around boto3 for the local MinIO S3 contract.

The internal client performs service-to-service operations.  A separate client
is built with the public endpoint so its presigned URLs contain a browser-
reachable host.  Runtime policies intentionally grant no DeleteObject action;
delete is disabled by default rather than relying on a remote AccessDenied.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.storage.interface import ObjectStat, PresignedRequest, StorageDeleteNotPermittedError


def _endpoint_url(value: str, *, secure: bool) -> str:
    value = value.rstrip("/")
    if value.startswith(("http://", "https://")):
        return value
    return f"{'https' if secure else 'http'}://{value}"


class Boto3MinioStorage:
    """Boto3-backed MinIO adapter with non-blocking async methods."""

    def __init__(
        self,
        *,
        internal_endpoint: str,
        public_endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        presigned_ttl_seconds: int = 600,
        region_name: str = "us-east-1",
        allow_delete: bool = False,
        internal_client: Any | None = None,
        public_client: Any | None = None,
    ) -> None:
        if not access_key or not secret_key:
            raise ValueError("MinIO service-account credentials are required")
        if access_key == "minio-root-admin":
            raise ValueError("MinIO root credentials must never be used at runtime")
        if presigned_ttl_seconds < 1:
            raise ValueError("presigned_ttl_seconds must be positive")

        self._ttl = presigned_ttl_seconds
        self._allow_delete = allow_delete
        common = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region_name,
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        self._internal = internal_client or boto3.client(
            "s3", endpoint_url=_endpoint_url(internal_endpoint, secure=secure), **common
        )
        self._public = public_client or boto3.client(
            "s3", endpoint_url=_endpoint_url(public_endpoint, secure=secure), **common
        )

        public_scheme = urlparse(_endpoint_url(public_endpoint, secure=secure)).scheme
        if public_scheme not in {"http", "https"}:
            raise ValueError("public MinIO endpoint must use HTTP or HTTPS")

    def _expiry(self, requested: int | None) -> int:
        expiry = self._ttl if requested is None else requested
        if expiry < 1 or expiry > self._ttl:
            raise ValueError(f"presigned URL expiry must be between 1 and {self._ttl} seconds")
        return expiry

    async def healthcheck(self) -> bool:
        """Check an ACL-authorized bucket without requiring admin ListAllBuckets."""

        await asyncio.to_thread(
            self._internal.list_objects_v2,
            Bucket="upload-quarantine",
            MaxKeys=1,
        )
        return True

    async def create_presigned_put(
        self,
        bucket: str,
        key: str,
        *,
        content_type: str,
        expires_in_seconds: int | None = None,
        checksum_sha256_base64: str | None = None,
    ) -> PresignedRequest:
        expiry = self._expiry(expires_in_seconds)
        params: dict[str, Any] = {"Bucket": bucket, "Key": key, "ContentType": content_type}
        headers = {"Content-Type": content_type}
        if checksum_sha256_base64:
            params["ChecksumSHA256"] = checksum_sha256_base64
            headers["x-amz-checksum-sha256"] = checksum_sha256_base64
        url = await asyncio.to_thread(
            self._public.generate_presigned_url,
            "put_object",
            Params=params,
            ExpiresIn=expiry,
            HttpMethod="PUT",
        )
        return PresignedRequest(url=url, headers=headers, expires_in_seconds=expiry)

    async def create_presigned_get(
        self,
        bucket: str,
        key: str,
        *,
        expires_in_seconds: int | None = None,
        version_id: str | None = None,
    ) -> PresignedRequest:
        expiry = self._expiry(expires_in_seconds)
        params: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if version_id:
            params["VersionId"] = version_id
        url = await asyncio.to_thread(
            self._public.generate_presigned_url,
            "get_object",
            Params=params,
            ExpiresIn=expiry,
            HttpMethod="GET",
        )
        return PresignedRequest(url=url, headers={}, expires_in_seconds=expiry)

    async def stat_object(self, bucket: str, key: str, *, version_id: str | None = None) -> ObjectStat:
        params: dict[str, Any] = {"Bucket": bucket, "Key": key, "ChecksumMode": "ENABLED"}
        if version_id:
            params["VersionId"] = version_id
        response = await asyncio.to_thread(self._internal.head_object, **params)
        return self._as_stat(bucket, key, response)

    async def object_exists(self, bucket: str, key: str, *, version_id: str | None = None) -> bool:
        try:
            await self.stat_object(bucket, key, version_id=version_id)
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = exc.response.get("Error", {}).get("Code")
            if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    async def get_object(self, bucket: str, key: str, *, version_id: str | None = None) -> bytes:
        params: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if version_id:
            params["VersionId"] = version_id
        response = await asyncio.to_thread(self._internal.get_object, **params)
        body = response["Body"]
        try:
            return await asyncio.to_thread(body.read)
        finally:
            close = getattr(body, "close", None)
            if close is not None:
                await asyncio.to_thread(close)

    async def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectStat:
        response = await asyncio.to_thread(
            self._internal.put_object,
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata=dict(metadata or {}),
        )
        return ObjectStat(
            bucket=bucket,
            key=key,
            size_bytes=len(data),
            etag=_strip_etag(response.get("ETag")),
            content_type=content_type,
            version_id=response.get("VersionId"),
            checksum_sha256_base64=response.get("ChecksumSHA256"),
            metadata=dict(metadata or {}),
        )

    async def copy_object(
        self, source_bucket: str, source_key: str, target_bucket: str, target_key: str
    ) -> ObjectStat:
        await asyncio.to_thread(
            self._internal.copy_object,
            Bucket=target_bucket,
            Key=target_key,
            CopySource={"Bucket": source_bucket, "Key": source_key},
            MetadataDirective="COPY",
        )
        return await self.stat_object(target_bucket, target_key)

    async def put_object_tags(self, bucket: str, key: str, tags: Mapping[str, str]) -> None:
        if not tags:
            raise ValueError("at least one object tag is required")
        await asyncio.to_thread(
            self._internal.put_object_tagging,
            Bucket=bucket,
            Key=key,
            Tagging={"TagSet": [{"Key": name, "Value": value} for name, value in sorted(tags.items())]},
        )

    async def remove_object(self, bucket: str, key: str, *, version_id: str | None = None) -> None:
        if not self._allow_delete:
            raise StorageDeleteNotPermittedError(
                "runtime MinIO policies grant no DeleteObject; use the retention workflow"
            )
        params: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if version_id:
            params["VersionId"] = version_id
        await asyncio.to_thread(self._internal.delete_object, **params)

    async def close(self) -> None:
        for client in {id(self._internal): self._internal, id(self._public): self._public}.values():
            close = getattr(client, "close", None)
            if close is not None:
                await asyncio.to_thread(close)

    @staticmethod
    def _as_stat(bucket: str, key: str, response: Mapping[str, Any]) -> ObjectStat:
        return ObjectStat(
            bucket=bucket,
            key=key,
            size_bytes=int(response.get("ContentLength", 0)),
            etag=_strip_etag(response.get("ETag")),
            content_type=response.get("ContentType"),
            version_id=response.get("VersionId"),
            checksum_sha256_base64=response.get("ChecksumSHA256"),
            metadata=dict(response.get("Metadata", {})),
        )


def _strip_etag(value: Any) -> str | None:
    return str(value).strip('"') if value is not None else None
