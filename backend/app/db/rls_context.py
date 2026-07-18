"""PostgreSQL row-level-security transaction context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_SET_RLS_CONTEXT = text(
    """
    SELECT
        set_config('app.employee_id', :employee_id, true),
        set_config('app.branch_id', :branch_id, true),
        set_config('app.is_admin', :is_admin, true)
    """
)


async def set_rls_context(
    session: AsyncSession,
    employee_id: UUID,
    branch_id: UUID,
    is_admin: bool = False,
) -> None:
    """Set transaction-local RLS values after strict UUID validation."""
    employee = UUID(str(employee_id))
    branch = UUID(str(branch_id))
    await session.execute(
        _SET_RLS_CONTEXT,
        {
            "employee_id": str(employee),
            "branch_id": str(branch),
            "is_admin": "true" if is_admin else "false",
        },
    )


@asynccontextmanager
async def rls_transaction(
    session: AsyncSession,
    employee_id: UUID,
    branch_id: UUID,
    is_admin: bool = False,
) -> AsyncIterator[AsyncSession]:
    """Open a transaction and install the fail-closed RLS session context.

    A worker must pass the originating active employee and that employee's
    branch; infrastructure RLS deliberately rejects service-only identities.
    """
    if session.in_transaction():
        raise RuntimeError("rls_transaction requires a session without an active transaction")
    async with session.begin():
        await set_rls_context(session, employee_id, branch_id, is_admin)
        yield session

