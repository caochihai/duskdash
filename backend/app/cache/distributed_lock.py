"""Owner-token Redis lock with TTL and atomic Lua release/extension."""

from __future__ import annotations

import secrets
from types import TracebackType

from redis.asyncio import Redis

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

_EXTEND_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('pexpire', KEYS[1], ARGV[2])
end
return 0
"""


class LockNotAcquiredError(RuntimeError):
    """Raised by the async context manager when another owner holds a lock."""


class RedisDistributedLock:
    """A non-reentrant lock. PostgreSQL remains authoritative for job state."""

    def __init__(
        self,
        client: Redis,
        resource: str,
        *,
        ttl_seconds: float = 30.0,
        key_prefix: str = "bank-ai",
        owner_token: str | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("lock TTL must be positive")
        if not resource or any(character.isspace() for character in resource):
            raise ValueError("lock resource must contain no whitespace")
        self._client = client
        self.key = f"{key_prefix}:lock:{resource}"
        self.owner_token = owner_token or secrets.token_urlsafe(32)
        self.ttl_milliseconds = max(1, int(ttl_seconds * 1000))
        self.acquired = False

    async def acquire(self) -> bool:
        self.acquired = bool(
            await self._client.set(self.key, self.owner_token, nx=True, px=self.ttl_milliseconds)
        )
        return self.acquired

    async def release(self) -> bool:
        if not self.acquired:
            return False
        return await self.release_owned()

    async def release_owned(self) -> bool:
        """Release a lease reconstructed from an owner token.

        HTTP lease operations are stateless between requests.  A caller can
        therefore rebuild the lock with the opaque token returned by the
        claim operation and still use the same atomic compare-and-delete
        script.  A stolen or stale token cannot release another owner's lock.
        """

        released = bool(await self._client.eval(_RELEASE_SCRIPT, 1, self.key, self.owner_token))
        self.acquired = False
        return released

    async def extend(self, *, ttl_seconds: float | None = None) -> bool:
        if not self.acquired:
            return False
        return await self.refresh(ttl_seconds=ttl_seconds)

    async def refresh(self, *, ttl_seconds: float | None = None) -> bool:
        """Extend a lease reconstructed from its opaque owner token."""

        ttl_ms = self.ttl_milliseconds if ttl_seconds is None else max(1, int(ttl_seconds * 1000))
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("lock TTL must be positive")
        extended = bool(
            await self._client.eval(_EXTEND_SCRIPT, 1, self.key, self.owner_token, str(ttl_ms))
        )
        if extended:
            self.ttl_milliseconds = ttl_ms
            self.acquired = True
        return extended

    async def __aenter__(self) -> RedisDistributedLock:
        if not await self.acquire():
            raise LockNotAcquiredError(f"lock is already held: {self.key}")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.release()
