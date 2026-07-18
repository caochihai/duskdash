"""Redis Pub/Sub adapter for ephemeral SSE fan-out only."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any
from uuid import UUID

from redis.asyncio import Redis


class SSEChannels:
    """Exact Redis channel names provisioned by the infrastructure contract."""

    @staticmethod
    def employee(employee_id: UUID, *, prefix: str = "bank-ai") -> str:
        return f"{prefix}:sse:employee:{employee_id}"

    @staticmethod
    def job(job_id: UUID, *, prefix: str = "bank-ai") -> str:
        return f"{prefix}:sse:job:{job_id}"

    @staticmethod
    def analysis(analysis_case_id: UUID, *, prefix: str = "bank-ai") -> str:
        return f"{prefix}:sse:analysis:{analysis_case_id}"


class RedisPubSub:
    """Publish and stream compact JSON signals; never durable job state."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def publish(self, channel: str, signal: Mapping[str, Any]) -> int:
        if not channel.startswith("bank-ai:sse:"):
            raise ValueError("only the bank-ai SSE namespace is permitted")
        payload = json.dumps(dict(signal), separators=(",", ":"), sort_keys=True, default=str)
        return int(await self._client.publish(channel, payload))

    async def subscribe(self, *channels: str) -> AsyncIterator[dict[str, Any]]:
        if not channels or any(not channel.startswith("bank-ai:sse:") for channel in channels):
            raise ValueError("at least one bank-ai SSE channel is required")
        pubsub = self._client.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(*channels)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode()
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    yield parsed
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
