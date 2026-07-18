"""Transaction helpers shared by API services and workers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Open a transaction, rejecting ambiguous nested ownership.

    Repositories intentionally never commit.  The application service owns
    the transaction containing business state, outbox and audit writes.
    """
    if session.in_transaction():
        raise RuntimeError("transaction() requires a session without an active transaction")
    async with session.begin():
        yield session

