"""Small SQLAlchemy Core helpers for repository implementations."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import TextClause, text
from sqlalchemy.ext.asyncio import AsyncSession

Params = Mapping[str, Any]
Record = dict[str, Any]


def _json_default(value: Any) -> str:
    if isinstance(value, (UUID, date, datetime)):
        return value.isoformat() if not isinstance(value, UUID) else str(value)
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")


def database_params(params: Params | None) -> dict[str, Any]:
    """Serialize JSON objects for untyped textual asyncpg bind parameters."""
    prepared: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if isinstance(value, (dict, list)):
            prepared[key] = json.dumps(value, default=_json_default, separators=(",", ":"))
        else:
            prepared[key] = value
    return prepared


def pagination(page: int, page_size: int) -> tuple[int, int]:
    if page < 1:
        raise ValueError("page must be at least 1")
    if not 1 <= page_size <= 200:
        raise ValueError("page_size must be between 1 and 200")
    return page_size, (page - 1) * page_size


def rows_with_total(rows: list[Record]) -> tuple[list[Record], int]:
    """Extract a ``count(*) OVER ()`` value from paginated query rows."""
    total = int(rows[0].get("total_count", 0)) if rows else 0
    for row in rows:
        row.pop("total_count", None)
    return rows, total


async def fetch_one(
    session: AsyncSession,
    statement: str | TextClause,
    params: Params | None = None,
) -> Record | None:
    result = await session.execute(
        text(statement) if isinstance(statement, str) else statement,
        database_params(params),
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def fetch_all(
    session: AsyncSession,
    statement: str | TextClause,
    params: Params | None = None,
) -> list[Record]:
    result = await session.execute(
        text(statement) if isinstance(statement, str) else statement,
        database_params(params),
    )
    return [dict(row) for row in result.mappings().all()]


async def execute_returning(
    session: AsyncSession,
    statement: str | TextClause,
    params: Params | None = None,
) -> Record | None:
    return await fetch_one(session, statement, params)


def require_fields(values: Mapping[str, Any], fields: Sequence[str]) -> None:
    missing = [name for name in fields if name not in values]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def insert_sql(table: str, values: Mapping[str, Any], allowed: frozenset[str]) -> TextClause:
    """Build a safe INSERT from a strict compile-time column whitelist."""
    columns = [name for name in values if name in allowed]
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unsupported {table} fields: {', '.join(sorted(unknown))}")
    if not columns:
        raise ValueError(f"No values supplied for {table}")
    names = ", ".join(columns)
    binds = ", ".join(f":{name}" for name in columns)
    return text(f"INSERT INTO {table} ({names}) VALUES ({binds}) RETURNING *")  # noqa: S608


def update_sql(
    table: str,
    values: Mapping[str, Any],
    allowed: frozenset[str],
    where: str,
) -> TextClause:
    """Build a safe UPDATE from a strict compile-time column whitelist."""
    columns = [name for name in values if name in allowed]
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unsupported {table} fields: {', '.join(sorted(unknown))}")
    if not columns:
        raise ValueError(f"No values supplied for {table}")
    assignments = ", ".join(f"{name} = :{name}" for name in columns)
    return text(f"UPDATE {table} SET {assignments} WHERE {where} RETURNING *")  # noqa: S608
