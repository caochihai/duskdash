"""Hàng đợi async tối giản trên Redis (thay Kafka cho triển khai 1 box).

Reliable pattern: BLMOVE main -> processing (atomic), xử lý, thành công thì LREM;
lỗi thì requeue kèm attempt+1, quá số lần thì đẩy dead-letter. At-least-once.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

import redis.asyncio as redis


class RedisQueue:
    def __init__(
        self,
        url: str,
        name: str,
        *,
        max_attempts: int = 3,
        block_seconds: float = 5.0,
    ) -> None:
        self._redis = redis.from_url(url, decode_responses=True)
        self._main = f"queue:{name}"
        self._processing = f"queue:{name}:processing"
        self._dead = f"queue:{name}:dead"
        self._max_attempts = max_attempts
        self._block = block_seconds

    async def enqueue(self, payload: dict) -> None:
        await self._redis.rpush(self._main, json.dumps(payload))

    async def run(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        """Vòng lặp worker — chạy mãi tới khi bị huỷ."""
        while True:
            raw = await self._redis.blmove(
                self._main, self._processing, self._block, "LEFT", "RIGHT"
            )
            if raw is None:
                continue
            try:
                await handler(json.loads(raw))
            except Exception as exc:  # noqa: BLE001 - mọi lỗi -> retry/dead-letter
                await self._handle_failure(raw, exc)
            finally:
                await self._redis.lrem(self._processing, 1, raw)

    async def _handle_failure(self, raw: str, exc: Exception) -> None:
        payload = json.loads(raw)
        attempt = int(payload.get("attempt", 0)) + 1
        payload["attempt"] = attempt
        payload["last_error"] = str(exc)[:500]
        if attempt >= self._max_attempts:
            await self._redis.rpush(self._dead, json.dumps(payload))
        else:
            await self._redis.rpush(self._main, json.dumps(payload))

    async def close(self) -> None:
        await self._redis.aclose()
