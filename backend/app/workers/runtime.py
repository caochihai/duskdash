"""Shared sequential consumer runtime with Inbox-before-offset semantics."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.messaging.event_envelope import EventEnvelope
from app.messaging.inbox_handler import InboxHandler
from app.messaging.kafka_consumer import JobStatusSnapshot, KafkaEventConsumer
from app.messaging.topic_registry import Topic

EventCallback = Callable[[EventEnvelope], Awaitable[UUID | None]]
SnapshotCallback = Callable[[JobStatusSnapshot], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    name: str
    principal: str
    group_id: str
    topics: frozenset[Topic]
    handled_event_types: frozenset[str]


class RunnableComponent(Protocol):
    async def run(self, stop_event: asyncio.Event) -> None: ...


class KafkaWorkerRuntime:
    def __init__(
        self,
        *,
        consumer: KafkaEventConsumer,
        inbox: InboxHandler,
        handlers: Mapping[str, EventCallback],
        snapshot_handler: SnapshotCallback | None = None,
    ) -> None:
        self._consumer = consumer
        self._inbox = inbox
        self._handlers = dict(handlers)
        self._snapshot_handler = snapshot_handler

    async def run(self, stop_event: asyncio.Event) -> None:
        async with self._consumer:
            async for message in self._consumer.messages():
                if stop_event.is_set():
                    break
                if isinstance(message.payload, JobStatusSnapshot):
                    if self._snapshot_handler is not None:
                        await self._snapshot_handler(message.payload)
                    await self._consumer.commit()
                    continue
                callback = self._handlers.get(message.payload.event_type)
                if callback is None:
                    # Independent analysis groups receive every command. Ignored
                    # types are expected and must not block the assigned type.
                    await self._consumer.commit()
                    continue
                await self._inbox.handle(message.payload, callback)
                await self._consumer.commit()


def run_cli(component_name: str, spec: WorkerSpec | None = None) -> None:
    """Load the application assembly without coupling workers to FastAPI.

    The supplied factory may be sync or async, receives ``spec`` when present,
    and must return a ``RunnableComponent``. This keeps credentials in the
    deployment environment and permits each process to use only its own ACL.
    """

    parser = argparse.ArgumentParser(prog=f"python -m app.workers.{component_name}")
    parser.add_argument(
        "--factory",
        required=True,
        help="Dotted runtime assembly factory in module:function form",
    )
    args = parser.parse_args()
    asyncio.run(_run_loaded_factory(args.factory, spec))


async def _run_loaded_factory(reference: str, spec: WorkerSpec | None) -> None:
    module_name, separator, attribute_name = reference.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("factory must use module:function notation")
    factory = getattr(importlib.import_module(module_name), attribute_name)
    created: Any = factory(spec) if spec is not None else factory()
    component = await created if inspect.isawaitable(created) else created
    if not hasattr(component, "run"):
        raise TypeError("worker factory must return an object with async run(stop_event)")
    stop_event = asyncio.Event()
    try:
        await component.run(stop_event)
    finally:
        stop_event.set()
