"""Masked account access through an RLS-protected account root."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, fetch_all, fetch_one


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_customer(self, customer_id: UUID) -> list[Record]:
        return await fetch_all(
            self.session,
            """
            SELECT DISTINCT a.id AS account_id, a.account_number_masked,
                   a.account_type, a.currency, a.branch_id, a.status,
                   a.opened_at, a.closed_at, a.current_balance,
                   a.balance_as_of, ah.holder_role
            FROM customer.customer AS c
            JOIN banking.account_holder AS ah ON ah.party_id = c.party_id
            JOIN banking.account AS a ON a.id = ah.account_id
            WHERE c.id = :customer_id
              AND (ah.valid_from IS NULL OR ah.valid_from <= CURRENT_DATE)
              AND (ah.valid_until IS NULL OR ah.valid_until >= CURRENT_DATE)
            ORDER BY a.opened_at DESC NULLS LAST, a.id
            """,
            {"customer_id": customer_id},
        )

    async def get(self, account_id: UUID) -> Record | None:
        return await fetch_one(
            self.session,
            """
            SELECT id AS account_id, account_number_masked, account_type,
                   currency, branch_id, status, opened_at, closed_at,
                   current_balance, balance_as_of, updated_at
            FROM banking.account WHERE id = :account_id
            """,
            {"account_id": account_id},
        )

