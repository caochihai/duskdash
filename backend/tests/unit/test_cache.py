from __future__ import annotations

from uuid import uuid4

import pytest

from app.cache.distributed_lock import RedisDistributedLock
from app.cache.pubsub import RedisPubSub, SSEChannels
from app.cache.redis_cache import RedisCache


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.set_calls: list[tuple[str, object, dict[str, object]]] = []
        self.eval_calls: list[tuple[object, ...]] = []
        self.published: list[tuple[str, str]] = []

    async def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def set(self, key: str, value: object, **kwargs: object) -> bool:
        self.set_calls.append((key, value, kwargs))
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = value if isinstance(value, bytes) else str(value).encode()
        return True

    async def delete(self, key: str) -> int:
        return int(self.values.pop(key, None) is not None)

    async def eval(self, *args: object) -> int:
        self.eval_calls.append(args)
        return 1

    async def publish(self, channel: str, payload: str) -> int:
        self.published.append((channel, payload))
        return 1

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_cache_requires_ttl_and_uses_exact_namespace() -> None:
    redis = FakeRedis()
    cache = RedisCache(redis)  # type: ignore[arg-type]
    await cache.set_json("customer:1", {"amount": "10.0000"}, ttl_seconds=30)
    assert redis.set_calls[0][0] == "bank-ai:cache:customer:1"
    assert redis.set_calls[0][2] == {"ex": 30}
    assert await cache.get_json("customer:1") == {"amount": "10.0000"}
    with pytest.raises(ValueError):
        await cache.set_json("bad", {}, ttl_seconds=0)


@pytest.mark.asyncio
async def test_lock_has_owner_token_ttl_and_lua_release() -> None:
    redis = FakeRedis()
    lock = RedisDistributedLock(
        redis,  # type: ignore[arg-type]
        "document:123",
        ttl_seconds=2,
        owner_token="owner-token",
    )
    assert await lock.acquire()
    assert redis.set_calls[0] == (
        "bank-ai:lock:document:123",
        "owner-token",
        {"nx": True, "px": 2000},
    )
    assert await lock.release()
    assert redis.eval_calls[-1][2:] == ("bank-ai:lock:document:123", "owner-token")


@pytest.mark.asyncio
async def test_lock_can_refresh_and_release_from_stateless_owner_token() -> None:
    redis = FakeRedis()
    lease = RedisDistributedLock(
        redis,  # type: ignore[arg-type]
        "customer-processing:123",
        ttl_seconds=300,
        owner_token="opaque-lease-token",
    )

    assert await lease.refresh(ttl_seconds=600)
    assert lease.acquired
    assert redis.eval_calls[-1][2:] == (
        "bank-ai:lock:customer-processing:123",
        "opaque-lease-token",
        "600000",
    )
    assert await lease.release_owned()
    assert not lease.acquired
    assert redis.eval_calls[-1][2:] == (
        "bank-ai:lock:customer-processing:123",
        "opaque-lease-token",
    )


@pytest.mark.asyncio
async def test_pubsub_uses_contracted_sse_channels() -> None:
    redis = FakeRedis()
    pubsub = RedisPubSub(redis)  # type: ignore[arg-type]
    job_id = uuid4()
    channel = SSEChannels.job(job_id)
    assert channel == f"bank-ai:sse:job:{job_id}"
    assert await pubsub.publish(channel, {"job_id": job_id, "status": "RUNNING"}) == 1
    assert redis.published[0][0] == channel
