"""Conversation and message persistence rooted in conversation RLS."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from app.compat import UTC
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning, fetch_all, fetch_one, insert_sql

_CONVERSATION_COLUMNS = frozenset(
    {
        "id",
        "employee_id",
        "active_customer_id",
        "active_loan_application_id",
        "title",
        "status",
        "started_at",
        "ended_at",
    }
)


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        employee_id: UUID,
        active_customer_id: UUID | None,
        active_loan_application_id: UUID | None,
        title: str | None,
    ) -> Record:
        values: dict[str, Any] = {
            "id": uuid4(),
            "employee_id": employee_id,
            "active_customer_id": active_customer_id,
            "active_loan_application_id": active_loan_application_id,
            "title": title,
            "status": "ACTIVE",
            "started_at": datetime.now(UTC),
            "ended_at": None,
        }
        row = await execute_returning(
            self.session,
            insert_sql("ai.conversation", values, _CONVERSATION_COLUMNS),
            values,
        )
        if row is None:
            raise RuntimeError("Conversation insert returned no row")
        return row

    async def get(self, conversation_id: UUID, *, employee_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT * FROM ai.conversation
            WHERE id = :conversation_id AND employee_id = :employee_id
            """,
            {"conversation_id": conversation_id, "employee_id": employee_id},
        )

    async def list_for_employee(
        self,
        *,
        employee_id: UUID,
        customer_id: UUID | None = None,
        loan_application_id: UUID | None = None,
        status: str | None = None,
    ) -> list[Record]:
        """List only conversations owned by one employee.

        The explicit owner predicate is intentional even though the table has
        RLS. Administrators can select more rows under the infrastructure RLS
        policy, while the chat product contract remains private per employee.
        """
        return await fetch_all(
            self.session,
            """
            SELECT *
            FROM ai.conversation
            WHERE employee_id = :employee_id
              AND (
                  CAST(:customer_id AS uuid) IS NULL
                  OR active_customer_id = CAST(:customer_id AS uuid)
              )
              AND (
                  CAST(:loan_application_id AS uuid) IS NULL
                  OR active_loan_application_id = CAST(:loan_application_id AS uuid)
              )
              AND (
                  CAST(:status AS varchar) IS NULL
                  OR status = CAST(:status AS varchar)
              )
            ORDER BY started_at DESC, id DESC
            """,
            {
                "employee_id": employee_id,
                "customer_id": customer_id,
                "loan_application_id": loan_application_id,
                "status": status,
            },
        )

    async def close(self, conversation_id: UUID, *, employee_id: UUID) -> Record | None:
        return await execute_returning(
            self.session,
            """
            UPDATE ai.conversation
            SET status = 'CLOSED', ended_at = :ended_at
            WHERE id = :conversation_id AND employee_id = :employee_id
            RETURNING *
            """,
            {
                "conversation_id": conversation_id,
                "employee_id": employee_id,
                "ended_at": datetime.now(UTC),
            },
        )

    async def set_active_customer(
        self,
        conversation_id: UUID,
        *,
        employee_id: UUID,
        customer_id: UUID,
    ) -> Record | None:
        return await execute_returning(
            self.session,
            """
            UPDATE ai.conversation
            SET active_customer_id = :customer_id
            WHERE id = :conversation_id AND employee_id = :employee_id
            RETURNING *
            """,
            {
                "conversation_id": conversation_id,
                "employee_id": employee_id,
                "customer_id": customer_id,
            },
        )

    async def update_title(
        self,
        conversation_id: UUID,
        *,
        employee_id: UUID,
        title: str,
    ) -> Record | None:
        return await execute_returning(
            self.session,
            """
            UPDATE ai.conversation
            SET title = :title
            WHERE id = :conversation_id AND employee_id = :employee_id
            RETURNING *
            """,
            {
                "conversation_id": conversation_id,
                "employee_id": employee_id,
                "title": title,
            },
        )

    async def messages(self, conversation_id: UUID, *, employee_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT m.*
            FROM ai.conversation AS c
            JOIN ai.message AS m ON m.conversation_id = c.id
            WHERE c.id = :conversation_id AND c.employee_id = :employee_id
            ORDER BY m.created_at, m.id
            """,
            {"conversation_id": conversation_id, "employee_id": employee_id},
        )

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
        metadata: Mapping[str, Any] | None = None,
    ) -> Record | None:
        normalized_sender_type = sender_type.strip().upper()
        if normalized_sender_type not in {"EMPLOYEE", "ASSISTANT"}:
            raise ValueError("sender_type must be EMPLOYEE or ASSISTANT")
        complexity = route.get("complexity_level")
        if complexity is not None and not 1 <= int(complexity) <= 4:
            raise ValueError("complexity_level must be between 1 and 4")
        analysis_case = route.get("analysis_case_id")
        payload = {
            "id": uuid4(),
            "conversation_id": conversation_id,
            "sender_type": normalized_sender_type,
            "sender_id": (
                employee_id
                if normalized_sender_type == "EMPLOYEE" and sender_id is None
                else sender_id
            ),
            "content": content,
            "created_at": datetime.now(UTC),
            "parent_message_id": parent_message_id,
            "route_type": route.get("route_type"),
            "complexity_level": complexity,
            "analysis_case_id": UUID(str(analysis_case)) if analysis_case else None,
            "metadata": dict(metadata) if metadata else None,
            "employee_id": employee_id,
        }
        row = await execute_returning(
            self.session,
            """
            INSERT INTO ai.message (
                id, conversation_id, sender_type, sender_id, content,
                created_at, parent_message_id, route_type, complexity_level,
                analysis_case_id, metadata
            )
            SELECT :id, c.id, :sender_type, :sender_id, :content,
                   :created_at, :parent_message_id, :route_type,
                   :complexity_level, :analysis_case_id, CAST(:metadata AS jsonb)
            FROM ai.conversation AS c
            WHERE c.id = :conversation_id AND c.employee_id = :employee_id
              AND (
                  CAST(:parent_message_id AS UUID) IS NULL
                  OR EXISTS (
                      SELECT 1
                      FROM ai.message AS parent
                      WHERE parent.id = CAST(:parent_message_id AS UUID)
                        AND parent.conversation_id = c.id
                  )
              )
            RETURNING *
            """,
            payload,
        )
        if row is None:
            return None

        # The infrastructure contract links documents only to customer, loan,
        # or collateral.  Keep the authorized selection in this turn response
        # without inventing a MESSAGE entity_type or changing the schema.
        normalized_attachment_ids = tuple(dict.fromkeys(attachment_ids))
        row["attachment_ids"] = list(normalized_attachment_ids)
        return row
