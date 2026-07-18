"""Internal API formatting helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel

from app.schemas.common import PageMeta, PaginatedResponse

ModelT = TypeVar("ModelT", bound=BaseModel)


def request_uuid(request: Request, name: str = "request_id") -> UUID | None:
    value = getattr(request.state, name, None)
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def page_response(
    model: type[ModelT],
    rows: Sequence[Mapping[str, Any]],
    *,
    page: int,
    page_size: int,
    total: int,
) -> PaginatedResponse[ModelT]:
    items = []
    for row in rows:
        payload = dict(row)
        payload.pop("total_count", None)
        items.append(model.model_validate(payload))
    return PaginatedResponse[ModelT](
        items=items,
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


def infer_total(rows: Sequence[Mapping[str, Any]]) -> int:
    if not rows:
        return 0
    return int(rows[0].get("total_count", len(rows)))
