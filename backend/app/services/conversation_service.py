"""Employee-owned conversations and schema-bound context routing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from app.schemas.conversation import ConversationReply
from app.services.access import require_permission
from app.services.protocols import PrincipalLike


class ConversationRepositoryLike(Protocol):
    async def create(
        self,
        *,
        employee_id: UUID,
        active_customer_id: UUID | None,
        active_loan_application_id: UUID | None,
        title: str | None,
    ) -> Mapping[str, Any]: ...

    async def get(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> Mapping[str, Any] | None: ...

    async def list_for_employee(
        self,
        *,
        employee_id: UUID,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
        status: str | None = None,
    ) -> Sequence[Mapping[str, Any]]: ...

    async def close(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> Mapping[str, Any] | None: ...

    async def update_title(
        self,
        conversation_id: UUID,
        *,
        employee_id: UUID,
        title: str,
    ) -> Mapping[str, Any] | None: ...

    async def messages(
        self, conversation_id: UUID, *, employee_id: UUID
    ) -> Sequence[Mapping[str, Any]]: ...

    async def add_message(
        self,
        conversation_id: UUID,
        *,
        employee_id: UUID,
        content: str,
        route: Mapping[str, Any],
        sender_type: str = "EMPLOYEE",
        sender_id: UUID | None = None,
        parent_message_id: UUID | None = None,
        attachment_ids: Sequence[UUID] = (),
    ) -> Mapping[str, Any] | None: ...


class ContextRouterLike(Protocol):
    async def authorize(
        self,
        *,
        employee_id: UUID,
        customer_id: UUID | None,
        loan_application_id: UUID | None,
        attachment_ids: tuple[UUID, ...] = (),
    ) -> tuple[frozenset[UUID], frozenset[UUID]]: ...

    async def route(
        self,
        *,
        employee_id: UUID,
        conversation: Mapping[str, Any],
        message: str,
        attachment_ids: Sequence[UUID],
    ) -> Mapping[str, Any]: ...


class ConversationResponder(Protocol):
    """Produce a structured, employee-facing answer after routing.

    Implementations may use deterministic tools, one expert, or a bounded
    multi-agent workflow.  They must return conclusions and source metadata,
    never private chain-of-thought.
    """

    async def respond(
        self,
        *,
        principal: PrincipalLike,
        conversation: Mapping[str, Any],
        message: str,
        route: Mapping[str, Any],
        attachment_ids: Sequence[UUID],
    ) -> ConversationReply | Mapping[str, Any]: ...


class CustomerProcessingGuardLike(Protocol):
    async def assert_can_process(
        self,
        principal: PrincipalLike,
        customer_id: UUID,
        *,
        lease_token: str | None = None,
    ) -> Mapping[str, Any]: ...


class LoanProcessingGuardLike(Protocol):
    async def require_assigned_handler(
        self,
        principal: PrincipalLike,
        loan_application_id: UUID,
    ) -> Mapping[str, Any]: ...


class ConversationProcessingGuardLike(Protocol):
    async def assert_can_process(
        self,
        principal: PrincipalLike,
        *,
        customer_id: UUID,
        loan_application_id: UUID | None,
        lease_token: str | None,
    ) -> None: ...


class ConversationProcessingGuard:
    """Reuse persistent customer/loan ownership checks for orchestrated chat work."""

    def __init__(
        self,
        customer_guard: CustomerProcessingGuardLike,
        loan_guard: LoanProcessingGuardLike,
    ) -> None:
        self._customer_guard = customer_guard
        self._loan_guard = loan_guard

    async def assert_can_process(
        self,
        principal: PrincipalLike,
        *,
        customer_id: UUID,
        loan_application_id: UUID | None,
        lease_token: str | None,
    ) -> None:
        if loan_application_id is not None:
            loan = await self._loan_guard.require_assigned_handler(
                principal, loan_application_id
            )
            if UUID(str(loan["primary_customer_id"])) != customer_id:
                raise PermissionError(
                    "Loan application does not belong to the active customer"
                )
        await self._customer_guard.assert_can_process(
            principal,
            customer_id,
            lease_token=lease_token,
        )


class ConversationService:
    def __init__(
        self,
        repository: ConversationRepositoryLike,
        context_router: ContextRouterLike,
        responder: ConversationResponder | None = None,
        processing_guard: ConversationProcessingGuardLike | None = None,
    ) -> None:
        self._repository = repository
        self._context_router = context_router
        self._responder = responder
        self._processing_guard = processing_guard

    async def create(
        self,
        principal: PrincipalLike,
        *,
        active_customer_id: UUID | None,
        active_loan_application_id: UUID | None,
        title: str | None,
    ) -> Mapping[str, Any]:
        if title and len(title) > 200:
            raise ValueError("Conversation title is too long")
        await self._context_router.authorize(
            employee_id=principal.employee_id,
            customer_id=active_customer_id,
            loan_application_id=active_loan_application_id,
        )
        return await self._repository.create(
            employee_id=principal.employee_id,
            active_customer_id=active_customer_id,
            active_loan_application_id=active_loan_application_id,
            title=title,
        )

    async def get(
        self, principal: PrincipalLike, conversation_id: UUID
    ) -> Mapping[str, Any]:
        row = await self._repository.get(conversation_id, employee_id=principal.employee_id)
        if row is None:
            raise LookupError("Conversation was not found")
        return row

    async def list(
        self,
        principal: PrincipalLike,
        *,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
        status: str | None = None,
    ) -> Sequence[Mapping[str, Any]]:
        normalized_status = status.strip().upper() if status is not None else None
        if normalized_status == "":
            raise ValueError("Conversation status cannot be empty")
        return await self._repository.list_for_employee(
            employee_id=principal.employee_id,
            customer_id=customer_id,
            loan_application_id=loan_application_id,
            status=normalized_status,
        )

    async def close(
        self, principal: PrincipalLike, conversation_id: UUID
    ) -> Mapping[str, Any]:
        conversation = await self.get(principal, conversation_id)
        if conversation.get("status") == "CLOSED":
            return conversation
        row = await self._repository.close(
            conversation_id,
            employee_id=principal.employee_id,
        )
        if row is None:
            raise RuntimeError("Conversation changed concurrently")
        return row

    async def update_title(
        self,
        principal: PrincipalLike,
        conversation_id: UUID,
        *,
        title: str,
    ) -> Mapping[str, Any]:
        clean_title = title.strip()
        if not clean_title or len(clean_title) > 200:
            raise ValueError("Conversation title must contain 1 to 200 characters")
        await self.get(principal, conversation_id)
        row = await self._repository.update_title(
            conversation_id,
            employee_id=principal.employee_id,
            title=clean_title,
        )
        if row is None:
            raise RuntimeError("Conversation changed concurrently")
        return row

    async def messages(
        self, principal: PrincipalLike, conversation_id: UUID
    ) -> Sequence[Mapping[str, Any]]:
        await self.get(principal, conversation_id)
        return await self._repository.messages(conversation_id, employee_id=principal.employee_id)

    async def add_message(
        self,
        principal: PrincipalLike,
        conversation_id: UUID,
        *,
        content: str,
        attachment_ids: Sequence[UUID],
        assignment_lease_token: str | None = None,
    ) -> Mapping[str, Any]:
        clean_content = content.strip()
        if not clean_content or len(clean_content) > 8000:
            raise ValueError("Message must contain 1 to 8000 characters")
        conversation = await self.get(principal, conversation_id)
        if str(conversation.get("status", "")).upper() == "CLOSED":
            raise ValueError("Cannot add a message to a closed conversation")
        normalized_attachment_ids = tuple(dict.fromkeys(attachment_ids))
        route = dict(
            await self._context_router.route(
                employee_id=principal.employee_id,
                conversation=conversation,
                message=clean_content,
                attachment_ids=normalized_attachment_ids,
            )
        )
        # Preserve the exact authorized selection even if an alternate router
        # implementation omits attachments from its semantic decision.
        route["attachment_ids"] = normalized_attachment_ids

        protected_analysis_routes = {"SINGLE_AGENT", "ORCHESTRATED"}
        if (
            self._responder is not None
            and str(route.get("route_type")) in protected_analysis_routes
        ):
            require_permission(principal, "loan:analyze")
            if self._processing_guard is None:
                raise RuntimeError(
                    "Conversation processing ownership guard is not configured"
                )
            customer_id = _required_context_uuid(
                route.get("customer_id") or conversation.get("active_customer_id"),
                "customer_id",
            )
            loan_application_id = _optional_context_uuid(
                route.get("loan_application_id")
                or conversation.get("active_loan_application_id"),
                "loan_application_id",
            )
            await self._processing_guard.assert_can_process(
                principal,
                customer_id=customer_id,
                loan_application_id=loan_application_id,
                lease_token=assignment_lease_token,
            )

        repository_options: dict[str, Any] = {}
        if normalized_attachment_ids:
            repository_options["attachment_ids"] = normalized_attachment_ids
        row = await self._repository.add_message(
            conversation_id,
            employee_id=principal.employee_id,
            content=clean_content,
            route=route,
            **repository_options,
        )
        if row is None:
            raise RuntimeError("Conversation changed concurrently")
        employee_message = {**dict(row), "route": route}
        if self._responder is None:
            return employee_message

        reply = await self._responder.respond(
            principal=principal,
            conversation=conversation,
            message=clean_content,
            route=route,
            attachment_ids=normalized_attachment_ids,
        )
        if not isinstance(reply, ConversationReply):
            reply = ConversationReply.model_validate(reply)

        assistant_route = dict(route)
        if reply.route_type is not None:
            assistant_route["route_type"] = reply.route_type
        if reply.complexity_level is not None:
            assistant_route["complexity_level"] = reply.complexity_level
        if reply.analysis_case_id is not None:
            assistant_route["analysis_case_id"] = reply.analysis_case_id

        assistant_row = await self._repository.add_message(
            conversation_id,
            employee_id=principal.employee_id,
            content=reply.content,
            route=assistant_route,
            sender_type="ASSISTANT",
            sender_id=None,
            parent_message_id=UUID(str(row["id"])),
        )
        if assistant_row is None:
            raise RuntimeError("Conversation changed concurrently")

        assistant_message = {**dict(assistant_row), "route": assistant_route}
        return {
            **employee_message,
            "assistant_message": assistant_message,
            "reply": reply.model_dump(mode="python"),
        }


def _required_context_uuid(value: Any, field_name: str) -> UUID:
    if value is None:
        raise ValueError(f"Orchestrated conversation requires {field_name}")
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Conversation {field_name} must be a UUID") from exc


def _optional_context_uuid(value: Any, field_name: str) -> UUID | None:
    if value is None:
        return None
    return _required_context_uuid(value, field_name)
