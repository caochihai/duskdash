"""Transaction listing and deterministic aggregate queries."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, fetch_all, fetch_one, pagination, rows_with_total


class TransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_customer(
        self,
        customer_id: UUID,
        page: int = 1,
        page_size: int = 50,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[Record], int]:
        limit, offset = pagination(page, page_size)
        rows = await fetch_all(
            self.session,
            """
            SELECT t.id AS transaction_id, t.account_id, t.booking_time,
                   t.value_date, t.direction, t.amount, t.currency,
                   t.transaction_type, t.channel, t.description,
                   t.balance_after, t.counterparty_name_masked,
                   t.reference_number, t.status, count(*) OVER () AS total_count
            FROM customer.customer AS c
            JOIN banking.account_holder AS ah ON ah.party_id = c.party_id
            JOIN banking.account AS a ON a.id = ah.account_id
            JOIN banking."transaction" AS t ON t.account_id = a.id
            WHERE c.id = :customer_id
              AND (CAST(:date_from AS DATE) IS NULL
                   OR t.booking_time >= CAST(:date_from AS DATE))
              AND (CAST(:date_to AS DATE) IS NULL
                   OR t.booking_time < CAST(:date_to AS DATE) + INTERVAL '1 day')
            ORDER BY t.booking_time DESC, t.id
            LIMIT :limit OFFSET :offset
            """,
            {
                "customer_id": customer_id,
                "date_from": date_from,
                "date_to": date_to,
                "limit": limit,
                "offset": offset,
            },
        )
        return rows_with_total(rows)

    async def summary(
        self,
        customer_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> Record:
        row = await fetch_one(
            self.session,
            """
            SELECT
                COALESCE(sum(t.amount) FILTER (WHERE t.direction = 'CREDIT'), 0)::numeric(24,4) AS total_inflow,
                COALESCE(sum(t.amount) FILTER (WHERE t.direction = 'DEBIT'), 0)::numeric(24,4) AS total_outflow,
                COALESCE(sum(t.amount) FILTER (
                    WHERE t.direction = 'CREDIT' AND t.transaction_type = 'SALARY'
                ), 0)::numeric(24,4) AS salary_inflow,
                count(*)::bigint AS transaction_count,
                min(t.booking_time) AS period_start,
                max(t.booking_time) AS period_end
            FROM customer.customer AS c
            JOIN banking.account_holder AS ah ON ah.party_id = c.party_id
            JOIN banking.account AS a ON a.id = ah.account_id
            JOIN banking."transaction" AS t ON t.account_id = a.id
            WHERE c.id = :customer_id
              AND (CAST(:date_from AS DATE) IS NULL
                   OR t.booking_time >= CAST(:date_from AS DATE))
              AND (CAST(:date_to AS DATE) IS NULL
                   OR t.booking_time < CAST(:date_to AS DATE) + INTERVAL '1 day')
            """,
            {"customer_id": customer_id, "date_from": date_from, "date_to": date_to},
        )
        return row or {
            "total_inflow": 0,
            "total_outflow": 0,
            "salary_inflow": 0,
            "transaction_count": 0,
            "period_start": None,
            "period_end": None,
        }
