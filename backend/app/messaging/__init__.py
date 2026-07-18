"""Kafka event contracts, adapters, and Outbox/Inbox coordination."""

from app.messaging.event_envelope import Actor, ActorType, EventEnvelope, EventMetadata, Resource
from app.messaging.topic_registry import Topic, TopicRegistry

__all__ = [
    "Actor",
    "ActorType",
    "EventEnvelope",
    "EventMetadata",
    "Resource",
    "Topic",
    "TopicRegistry",
]
