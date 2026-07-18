"""Async SQLAlchemy engine and session lifecycle.

The application connects as the infrastructure-owned ``bank_app`` (or
``bank_worker`` in worker processes) role.  This module never creates schema
objects; Flyway migrations under ``infra/database`` remain authoritative.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings

__all__ = [
    "AsyncSessionFactory",
    "async_engine",
    "close_db",
    "create_session_factory",
    "get_async_session",
    "init_db",
]

async_engine: AsyncEngine | None = None
AsyncSessionFactory: async_sessionmaker[AsyncSession] | None = None


def _asyncpg_url(value: str) -> URL:
    """Normalize the infrastructure PostgreSQL URL to the asyncpg dialect."""
    url = make_url(value)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")
    if url.drivername != "postgresql+asyncpg":
        raise ValueError("DATABASE_URL must use PostgreSQL with asyncpg")
    return url


def create_session_factory(
    settings: Settings | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create an engine/factory pair from :class:`Settings`.

    Keeping construction separate makes the database layer testable without
    mutating the module-level application lifecycle state.
    """
    effective = settings or get_settings()
    engine = create_async_engine(
        _asyncpg_url(effective.database_async_url),
        echo=effective.database_echo,
        pool_size=effective.database_pool_size,
        max_overflow=effective.database_pool_max_overflow,
        pool_timeout=effective.database_pool_timeout,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, factory


async def init_db(settings: Settings | None = None) -> None:
    """Initialize the process-wide engine and session factory once."""
    global async_engine, AsyncSessionFactory
    if async_engine is not None:
        return
    async_engine, AsyncSessionFactory = create_session_factory(settings)


async def close_db() -> None:
    """Dispose the process-wide connection pool."""
    global async_engine, AsyncSessionFactory
    if async_engine is not None:
        await async_engine.dispose()
    async_engine = None
    AsyncSessionFactory = None


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a rollback-safe async session."""
    if AsyncSessionFactory is None:
        raise RuntimeError("Database is not initialized; call init_db() first")
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
