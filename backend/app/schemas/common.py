"""Shared API response conventions."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

T = TypeVar("T")


def serialize_decimal(value: Decimal) -> str:
    """Serialize a decimal without ever converting through binary float."""

    return format(value, "f")


DecimalString = Annotated[Decimal, PlainSerializer(serialize_decimal, return_type=str, when_used="json")]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Money(APIModel):
    amount: DecimalString
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @field_validator("amount")
    @classmethod
    def normalize_scale(cls, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)


class PageMeta(APIModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class PaginatedResponse(APIModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class ErrorDetail(APIModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str


class ErrorResponse(APIModel):
    error: ErrorDetail
