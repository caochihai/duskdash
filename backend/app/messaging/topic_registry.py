"""Immutable topic, event-routing, ACL, and consumer-group registry."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from app.compat import StrEnum
from types import MappingProxyType
from typing import Final


class Topic(StrEnum):
    DOCUMENT_COMMANDS = "bank.document.commands.v1"
    DOCUMENT_EVENTS = "bank.document.events.v1"
    ANALYSIS_COMMANDS = "bank.analysis.commands.v1"
    ANALYSIS_EVENTS = "bank.analysis.events.v1"
    REPORT_COMMANDS = "bank.report.commands.v1"
    REPORT_EVENTS = "bank.report.events.v1"
    NOTIFICATION_EVENTS = "bank.notification.events.v1"
    JOB_STATUS = "bank.job-status.v1"
    AUDIT_EVENTS = "bank.audit.events.v1"
    RETRY_1M = "bank.retry.1m.v1"
    RETRY_10M = "bank.retry.10m.v1"
    DEAD_LETTER = "bank.dead-letter.v1"


@dataclass(frozen=True, slots=True)
class TopicSpec:
    partitions: int
    replication_factor: int
    retention_ms: int
    cleanup_policy: str = "delete"
    max_message_bytes: int = 1_048_576


_DAY = 86_400_000
TOPIC_SPECS: Final[Mapping[Topic, TopicSpec]] = MappingProxyType(
    {
        Topic.DOCUMENT_COMMANDS: TopicSpec(3, 1, 7 * _DAY),
        Topic.DOCUMENT_EVENTS: TopicSpec(3, 1, 30 * _DAY),
        Topic.ANALYSIS_COMMANDS: TopicSpec(3, 1, 7 * _DAY),
        Topic.ANALYSIS_EVENTS: TopicSpec(3, 1, 30 * _DAY),
        Topic.REPORT_COMMANDS: TopicSpec(3, 1, 7 * _DAY),
        Topic.REPORT_EVENTS: TopicSpec(3, 1, 30 * _DAY),
        Topic.NOTIFICATION_EVENTS: TopicSpec(3, 1, 3 * _DAY),
        Topic.JOB_STATUS: TopicSpec(3, 1, 7 * _DAY, "compact,delete"),
        Topic.AUDIT_EVENTS: TopicSpec(3, 1, 30 * _DAY),
        Topic.RETRY_1M: TopicSpec(3, 1, 7 * _DAY),
        Topic.RETRY_10M: TopicSpec(3, 1, 7 * _DAY),
        Topic.DEAD_LETTER: TopicSpec(3, 1, 30 * _DAY),
    }
)

DOCUMENT_COMMANDS = frozenset(
    {
        "document.processing.requested",
        "document.security-scan.requested",
        "document.ocr.requested",
        "document.classification.requested",
        "document.extraction.requested",
        "document.embedding.requested",
    }
)
DOCUMENT_EVENTS = frozenset(
    {
        "document.processing.started",
        "document.security-scan.completed",
        "document.ocr.completed",
        "document.classification.completed",
        "document.extraction.completed",
        "document.embedding.completed",
        "document.processing.completed",
        "document.processing.failed",
    }
)
ANALYSIS_COMMANDS = frozenset(
    {
        "analysis.requested",
        "analysis.document-agent.requested",
        "analysis.credit-agent.requested",
        "analysis.compliance-agent.requested",
        "analysis.validation.requested",
        "analysis.synthesis.requested",
    }
)
ANALYSIS_EVENTS = frozenset(
    {
        "analysis.started",
        "analysis.plan.created",
        "analysis.task.started",
        "analysis.task.completed",
        "finding.created",
        "analysis.validation.completed",
        "analysis.completed",
        "analysis.failed",
    }
)
REPORT_COMMANDS = frozenset({"report.generation.requested", "report.pdf.requested"})
REPORT_EVENTS = frozenset(
    {
        "report.generation.started",
        "report.generated",
        "report.pdf.generated",
        "report.generation.failed",
    }
)
NOTIFICATION_EVENTS = frozenset(
    {"job.progress.updated", "job.completed", "job.failed", "notification.created"}
)

EVENT_TOPICS: Final[Mapping[str, Topic]] = MappingProxyType(
    {
        **dict.fromkeys(DOCUMENT_COMMANDS, Topic.DOCUMENT_COMMANDS),
        **dict.fromkeys(DOCUMENT_EVENTS, Topic.DOCUMENT_EVENTS),
        **dict.fromkeys(ANALYSIS_COMMANDS, Topic.ANALYSIS_COMMANDS),
        **dict.fromkeys(ANALYSIS_EVENTS, Topic.ANALYSIS_EVENTS),
        **dict.fromkeys(REPORT_COMMANDS, Topic.REPORT_COMMANDS),
        **dict.fromkeys(REPORT_EVENTS, Topic.REPORT_EVENTS),
        **dict.fromkeys(NOTIFICATION_EVENTS, Topic.NOTIFICATION_EVENTS),
    }
)

PRODUCE_ACL: Final[Mapping[str, frozenset[Topic]]] = MappingProxyType(
    {
        "bank-api": frozenset({Topic.DOCUMENT_COMMANDS, Topic.ANALYSIS_COMMANDS, Topic.REPORT_COMMANDS}),
        "document-worker": frozenset(
            {
                Topic.DOCUMENT_EVENTS,
                Topic.NOTIFICATION_EVENTS,
                Topic.JOB_STATUS,
                Topic.RETRY_1M,
                Topic.RETRY_10M,
                Topic.DEAD_LETTER,
            }
        ),
        "analysis-orchestrator": frozenset(
            {Topic.ANALYSIS_COMMANDS, Topic.ANALYSIS_EVENTS, Topic.NOTIFICATION_EVENTS}
        ),
        "credit-worker": frozenset(
            {Topic.ANALYSIS_EVENTS, Topic.NOTIFICATION_EVENTS, Topic.DEAD_LETTER}
        ),
        "compliance-worker": frozenset(
            {Topic.ANALYSIS_EVENTS, Topic.NOTIFICATION_EVENTS, Topic.DEAD_LETTER}
        ),
        "report-worker": frozenset({Topic.REPORT_EVENTS, Topic.NOTIFICATION_EVENTS}),
        "notification-gateway": frozenset(),
        "audit-consumer": frozenset(),
    }
)

CONSUMER_ACL: Final[Mapping[str, tuple[str, frozenset[Topic]]]] = MappingProxyType(
    {
        "document-worker": ("document-worker-group", frozenset({Topic.DOCUMENT_COMMANDS})),
        "analysis-orchestrator": (
            "analysis-orchestrator-group",
            frozenset({Topic.ANALYSIS_COMMANDS, Topic.DOCUMENT_EVENTS}),
        ),
        "credit-worker": ("credit-worker-group", frozenset({Topic.ANALYSIS_COMMANDS})),
        "compliance-worker": ("compliance-worker-group", frozenset({Topic.ANALYSIS_COMMANDS})),
        "report-worker": (
            "report-worker-group",
            frozenset({Topic.REPORT_COMMANDS, Topic.ANALYSIS_EVENTS}),
        ),
        "notification-gateway": (
            "notification-gateway-group",
            frozenset({Topic.NOTIFICATION_EVENTS, Topic.JOB_STATUS}),
        ),
        "audit-consumer": (
            "audit-consumer-group",
            frozenset(
                {Topic.AUDIT_EVENTS, Topic.DOCUMENT_EVENTS, Topic.ANALYSIS_EVENTS, Topic.REPORT_EVENTS}
            ),
        ),
    }
)


class TopicContractError(ValueError):
    """Raised before a client makes a request forbidden by the infra ACL."""


class TopicRegistry:
    """Pure validation helpers shared by producers, consumers, and tests."""

    @staticmethod
    def topic_for_event(event_type: str) -> Topic:
        try:
            return EVENT_TOPICS[event_type]
        except KeyError as exc:
            raise TopicContractError(f"event type has no infrastructure topic mapping: {event_type}") from exc

    @staticmethod
    def assert_can_produce(principal: str, topic: Topic | str) -> Topic:
        topic_value = Topic(topic)
        if principal == "kafka-admin":
            raise TopicContractError("Kafka admin credentials are forbidden at runtime")
        if topic_value not in PRODUCE_ACL.get(principal, frozenset()):
            raise TopicContractError(f"{principal} has no WRITE ACL for {topic_value}")
        return topic_value

    @staticmethod
    def assert_can_consume(principal: str, group_id: str, topics: set[Topic] | frozenset[Topic]) -> None:
        try:
            expected_group, allowed_topics = CONSUMER_ACL[principal]
        except KeyError as exc:
            raise TopicContractError(f"{principal} has no consumer ACL") from exc
        if group_id != expected_group:
            raise TopicContractError(f"{principal} must use exact consumer group {expected_group}")
        denied = topics - allowed_topics
        if denied:
            names = ", ".join(sorted(str(topic) for topic in denied))
            raise TopicContractError(f"{principal} cannot consume: {names}")

    @staticmethod
    def validate_event_topic(event_type: str, resource_type: str, schema_name: str, topic: Topic | str) -> None:
        topic_value = Topic(topic)
        if topic_value in {Topic.RETRY_1M, Topic.RETRY_10M, Topic.DEAD_LETTER, Topic.AUDIT_EVENTS}:
            return
        expected = TopicRegistry.topic_for_event(event_type)
        if expected != topic_value:
            raise TopicContractError(f"{event_type} belongs on {expected}, not {topic_value}")
        if topic_value in {Topic.DOCUMENT_COMMANDS, Topic.DOCUMENT_EVENTS}:
            if resource_type != "DOCUMENT_VERSION" or not re.fullmatch(r"document\.[a-z0-9.-]+\.v1", schema_name):
                raise TopicContractError("document events require DOCUMENT_VERSION and document.*.v1 schema")
        elif topic_value in {Topic.ANALYSIS_COMMANDS, Topic.ANALYSIS_EVENTS}:
            if resource_type not in {"ANALYSIS_CASE", "ANALYSIS_TASK", "FINDING"}:
                raise TopicContractError("analysis event resource type is not allowed")
            if not re.fullmatch(r"(analysis|finding)\.[a-z0-9.-]+\.v1", schema_name):
                raise TopicContractError("analysis event schema name is not allowed")
        elif topic_value in {Topic.REPORT_COMMANDS, Topic.REPORT_EVENTS}:
            if resource_type != "REPORT" or not re.fullmatch(r"report\.[a-z0-9.-]+\.v1", schema_name):
                raise TopicContractError("report events require REPORT and report.*.v1 schema")
        elif topic_value is Topic.NOTIFICATION_EVENTS:
            if resource_type not in {"BACKGROUND_JOB", "NOTIFICATION", "EMPLOYEE"}:
                raise TopicContractError("notification event resource type is not allowed")
            if not re.fullmatch(r"(job|notification)\.[a-z0-9.-]+\.v1", schema_name):
                raise TopicContractError("notification event schema name is not allowed")
