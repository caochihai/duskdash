"""Durable job reads and Redis-backed Server-Sent Events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import PrincipalDep, get_job_service, require_state_adapter
from app.cache.pubsub import RedisPubSub, SSEChannels
from app.schemas.job import JobEventResponse, JobResponse, JobStepResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    principal: PrincipalDep,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    return JobResponse.model_validate(await service.get(principal, job_id))


@router.get("/{job_id}/steps", response_model=list[JobStepResponse])
async def get_job_steps(
    job_id: UUID,
    principal: PrincipalDep,
    service: Annotated[JobService, Depends(get_job_service)],
) -> list[JobStepResponse]:
    return [JobStepResponse.model_validate(row) for row in await service.steps(principal, job_id)]


@router.get("/{job_id}/events", response_model=list[JobEventResponse])
async def get_job_events(
    job_id: UUID,
    principal: PrincipalDep,
    service: Annotated[JobService, Depends(get_job_service)],
    after_sequence: int = Query(default=-1, ge=-1),
) -> list[JobEventResponse]:
    return [
        JobEventResponse.model_validate(row)
        for row in await service.events(
            principal,
            job_id,
            after_sequence=after_sequence,
        )
    ]


def _sse_message(
    payload: dict[str, Any], *, event: str, event_id: int | None = None
) -> bytes:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(
        "data: "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    )
    return ("\n".join(lines) + "\n\n").encode()


@router.get("/{job_id}/stream", response_class=StreamingResponse)
async def stream_job_events(
    job_id: UUID,
    request: Request,
    principal: PrincipalDep,
    service: Annotated[JobService, Depends(get_job_service)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    # Authorize and load durable replay before opening the ephemeral Redis subscription.
    await service.get(principal, job_id)
    try:
        after_sequence = int(last_event_id) if last_event_id is not None else -1
    except ValueError:
        after_sequence = -1
    backlog = await service.events(principal, job_id, after_sequence=after_sequence)
    pubsub = require_state_adapter(request, "redis_pubsub")
    if not isinstance(pubsub, RedisPubSub):
        raise RuntimeError("Redis SSE adapter is not configured")

    async def generate() -> AsyncIterator[bytes]:
        for row in backlog:
            data = dict(row)
            sequence = int(data.get("sequence_number", -1))
            yield _sse_message(data, event=str(data.get("event_type", "job.event")), event_id=sequence)
        channel = SSEChannels.job(job_id)
        async for signal in pubsub.subscribe(channel):
            if await request.is_disconnected():
                break
            yield _sse_message(signal, event="job.progress")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
