# Redis usage contract

Redis is an authenticated, bounded, temporary data store. It improves latency
and coordinates live instances; it is never the authoritative store for a job,
OCR result, agent result, report, official decision or audit record. Those remain
in PostgreSQL. Kafka remains the durable asynchronous transport.

## Required server configuration

```text
requirepass <REDIS_PASSWORD from .env.local>
appendonly yes
appendfsync everysec
save 900 1
save 300 10
save 60 10000
maxmemory 512mb
maxmemory-policy allkeys-lru
```

The host mapping `localhost:6379` is local-development only. Internal clients use
`redis:6379`, authenticate with `REDIS_PASSWORD`, select database 0 and apply the
`bank-ai` key prefix. Production keeps Redis on a private network and should use
transport encryption supported by its deployment platform.

## Key namespaces

| Pattern | Purpose | Required behavior |
| --- | --- | --- |
| `bank-ai:cache:*` | Short-lived query/JWKS-derived result cache | Explicit TTL; key contains no direct PII; safe to evict/rebuild |
| `bank-ai:lock:*` | Distributed lock | TTL, random owner token, Lua compare-and-delete release |
| `bank-ai:rate-limit:*` | Rate-limit counters | Atomic increment and expiry; durable enforcement/audit remains outside Redis |
| `bank-ai:sse:*` | Connection/presence metadata supporting live delivery | TTL and rebuild on reconnect; durable event history in PostgreSQL |
| `bank-ai:jwks:*` | Keycloak JWKS cache | TTL shorter than accepted key-rotation window; refresh on unknown `kid` |

Keys must use opaque UUIDs or hashes, never names, full identifiers, account
numbers, email addresses, tokens or secrets. Values must not contain access or
refresh tokens in logs/metrics.

## Safe distributed locks

Acquisition uses an unpredictable owner token and an expiry in one atomic
operation:

```text
SET bank-ai:lock:{resource_id} {owner_token} NX PX {ttl_ms}
```

The holder renews only if it still owns the lock. Release is an atomic Lua
compare-and-delete, never a separate `GET` and `DEL`:

```lua
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
```

A lock limits concurrent work; it does not provide exactly-once effects.
Database transactions, unique constraints and `integration.event_inbox` remain
mandatory. Choose TTL longer than the normal critical section but bounded so a
crashed owner cannot hold it indefinitely.

## SSE fan-out

Allowed Pub/Sub channels are:

```text
bank-ai:sse:employee:{employee_id}
bank-ai:sse:job:{job_id}
bank-ai:sse:analysis:{analysis_case_id}
```

A worker first commits job state and `integration.job_event` in PostgreSQL, then
the outbox/Kafka path delivers the notification. A notification gateway may
publish a minimal wake-up message to Redis. Backend instances subscribed to that
channel push SSE to connected clients. If a subscriber disconnects or Redis is
restarted, the client resumes from PostgreSQL job state/history. Redis Pub/Sub is
not used as a durable business queue.

## Cache and rate-limit rules

- Every cache entry has an explicit TTL and invalidation/rebuild strategy.
- Cache authorization-sensitive data only under an employee/scope-aware key;
  never reuse a result across customers or branches without rechecking access.
- Cache misses and eviction must not change business correctness.
- Rate-limit updates use atomic commands/scripts, set expiry on first use, and
  fail according to a documented endpoint policy if Redis is unavailable.
- JWKS lookup always validates issuer, audience, signature, expiry and expected
  algorithms; caching never weakens JWT validation.

## Verification and operations

The smoke test first proves unauthenticated `PING` is rejected, then authenticates
with `REDIS_PASSWORD` and expects `PONG`. Prometheus tracks memory usage, cache
hit/miss rate, evictions, connections and command latency through the internal
Redis exporter. Investigate sustained eviction or latency before increasing
memory; unbounded/missing TTL keys are usually the first fault to correct.

AOF/RDB settings improve local restart behavior but are not a substitute for
PostgreSQL backup. Redis data can be rebuilt; disaster recovery prioritizes the
business database and object store.
