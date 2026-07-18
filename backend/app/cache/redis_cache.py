"""Small async Redis cache that keeps PostgreSQL as the source of truth."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from redis.asyncio import Redis


class RedisCache:
    """Namespaced JSON/byte cache with mandatory TTLs."""

    _ALLOWED_NAMESPACES = frozenset({"cache", "jwks", "rate-limit"})

    def __init__(self, client: Redis, *, key_prefix: str = "bank-ai", namespace: str = "cache") -> None:
        if namespace not in self._ALLOWED_NAMESPACES:
            raise ValueError(f"unsupported Redis namespace: {namespace}")
        if not key_prefix or any(character.isspace() for character in key_prefix):
            raise ValueError("Redis key prefix must be non-empty and contain no whitespace")
        self._client = client
        self._base = f"{key_prefix}:{namespace}"

    def key(self, logical_key: str) -> str:
        if not logical_key or any(character.isspace() for character in logical_key):
            raise ValueError("Redis logical key must be non-empty and contain no whitespace")
        return f"{self._base}:{logical_key}"

    async def get_bytes(self, logical_key: str) -> bytes | None:
        value = await self._client.get(self.key(logical_key))
        if value is None:
            return None
        return value.encode() if isinstance(value, str) else bytes(value)

    async def set_bytes(self, logical_key: str, value: bytes, *, ttl_seconds: int) -> None:
        _require_ttl(ttl_seconds)
        await self._client.set(self.key(logical_key), value, ex=ttl_seconds)

    async def get_json(self, logical_key: str) -> Any | None:
        value = await self.get_bytes(logical_key)
        return None if value is None else json.loads(value)

    async def set_json(self, logical_key: str, value: Any, *, ttl_seconds: int) -> None:
        encoded = json.dumps(
            value,
            default=_json_default,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        await self.set_bytes(logical_key, encoded, ttl_seconds=ttl_seconds)

    async def delete(self, logical_key: str) -> bool:
        return bool(await self._client.delete(self.key(logical_key)))

    async def increment(self, logical_key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        """Increment a short-lived counter and set TTL only on first creation."""

        _require_ttl(ttl_seconds)
        if amount < 1:
            raise ValueError("counter increment must be positive")
        key = self.key(logical_key)
        async with self._client.pipeline(transaction=True) as pipeline:
            pipeline.incrby(key, amount)
            pipeline.expire(key, ttl_seconds, nx=True)
            results = await pipeline.execute()
        return int(results[0])

    async def close(self) -> None:
        await self._client.aclose()


def _require_ttl(ttl_seconds: int) -> None:
    if ttl_seconds < 1:
        raise ValueError("Redis cache entries must have a positive TTL")


def _json_default(value: Any) -> str:
    if isinstance(value, (UUID, Decimal, date, datetime)):
        return str(value)
    raise TypeError(f"value of type {type(value).__name__} is not JSON serializable")
