"""Conversation and context-router contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import APIModel


class ConversationCreateRequest(APIModel):
    active_customer_id: UUID | None = None
    active_loan_application_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)


class ConversationUpdateRequest(APIModel):
    title: str = Field(min_length=1, max_length=200, pattern=r".*\S.*")


class ConversationMessageRequest(APIModel):
    content: str = Field(min_length=1, max_length=8000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=20)


class ConversationResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    employee_id: UUID
    active_customer_id: UUID | None = None
    active_loan_application_id: UUID | None = None
    title: str | None = None
    status: str
    started_at: datetime
    ended_at: datetime | None = None


class MessageResponse(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: UUID
    conversation_id: UUID
    sender_type: str
    content: str
    route: dict[str, Any] | None = None
    attachment_ids: list[UUID] = Field(default_factory=list)


class ConversationReply(APIModel):
    """Structured responder output safe to expose to a bank employee.

    ``metadata`` intentionally carries only inspectable output such as
    citations and validation status.  Private model reasoning is never part
    of the conversation contract or persisted as a message.
    """

    content: str = Field(min_length=1, max_length=16_000)
    route_type: str | None = Field(default=None, max_length=30)
    complexity_level: int | None = Field(default=None, ge=1, le=4)
    analysis_case_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("Reply content cannot be empty")
        return clean_value

    @field_validator("metadata")
    @classmethod
    def reject_private_reasoning(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden_keys = {
            "chain_of_thought",
            "chainofthought",
            "internal_reasoning",
            "private_reasoning",
            "scratchpad",
            "thought_process",
        }

        def contains_forbidden_key(candidate: Any) -> bool:
            if isinstance(candidate, dict):
                for key, nested_value in candidate.items():
                    normalized_key = str(key).casefold().replace("-", "_")
                    if normalized_key in forbidden_keys or contains_forbidden_key(
                        nested_value
                    ):
                        return True
            elif isinstance(candidate, (list, tuple)):
                return any(contains_forbidden_key(item) for item in candidate)
            return False

        if contains_forbidden_key(value):
            raise ValueError("Private model reasoning cannot be included in a reply")
        return value


class ConversationTurnResponse(MessageResponse):
    """Additive response for a user message and its optional assistant reply."""

    assistant_message: MessageResponse | None = None
    reply: ConversationReply | None = None
