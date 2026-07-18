"""Database session management for async SQLAlchemy 2.

Provides:
- ``AsyncSessionFactory``: configured sessionmaker bound to the engine.
- ``get_async_session()``: FastAPI-compatible dependency that yields a session.
- ``init_db()`` / ``close_db()``: called during application lifespan.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

__all__ = [
    "async_engine",
    "AsyncSessionFactory",
    "get_async_session",
    "init_db",
    "close_db",
]

# ---------------------------------------------------------------------------
# Module-level singletons – initialised lazily via ``init_db()``
# ---------------------------------------------------------------------------
async_engine: AsyncEngine | None = None
AsyncSessionFactory: async_sessionmaker[AsyncSession] | None = None


def _build_url() -> str:
    """Build the async database URL from environment variables.

    Reads the same env vars exposed in ``backend-connections.env.example``.
    The URL *must* use the ``postgresql+asyncpg://`` scheme.
    """
    import os

    url = os.environ.get("DATABASE_URL", "")
    # The infra contract provides ``postgresql://`` – we need ``postgresql+asyncpg://``
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url

    # Fallback: construct from individual parts
    host = os.environ.get("DATABASE_HOST", "localhost")
    port = os.environ.get("DATABASE_PORT", "5432")
    name = os.environ.get("DATABASE_NAME", "bank_ai")
    user = os.environ.get("DATABASE_USER", "bank_app")
    password = os.environ.get("DATABASE_PASSWORD", "")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


async def init_db() -> None:
    """Create the async engine and session factory.

    Must be called once at application startup (e.g. in FastAPI lifespan).
    """
    global async_engine, AsyncSessionFactory  # noqa: PLW0603

    url = _build_url()

    async_engine = create_async_engine(
        url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    AsyncSessionFactory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_db() -> None:
    """Dispose of the engine connection pool.

    Must be called once at application shutdown (e.g. in FastAPI lifespan).
    """
    global async_engine, AsyncSessionFactory  # noqa: PLW0603

    if async_engine is not None:
        await async_engine.dispose()
        async_engine = None
    AsyncSessionFactory = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an ``AsyncSession``.

    The session is *not* auto-committed; callers are expected to commit
    explicitly (or use the ``transactional`` helper from ``transaction.py``).
    """
    if AsyncSessionFactory is None:
        raise RuntimeError(
            "Database has not been initialised. Call init_db() first."
        )

    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
