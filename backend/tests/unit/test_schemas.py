"""Shared API schema convention tests."""

from decimal import Decimal

import pytest
from pydantic import BaseModel

from app.schemas.common import DecimalString, ErrorDetail, ErrorResponse, Money, PageMeta, PaginatedResponse


class DecimalPayload(BaseModel):
    value: DecimalString


@pytest.mark.unit
def test_money_is_serialized_as_fixed_scale_string() -> None:
    payload = Money(amount=Decimal("700000000"), currency="VND")

    assert payload.model_dump(mode="json") == {"amount": "700000000.0000", "currency": "VND"}


@pytest.mark.unit
def test_generic_decimal_never_becomes_binary_float() -> None:
    payload = DecimalPayload(value=Decimal("0.61360000"))

    assert payload.model_dump(mode="json")["value"] == "0.61360000"


@pytest.mark.unit
def test_paginated_response_contract() -> None:
    response = PaginatedResponse[str](
        items=["item"],
        meta=PageMeta(page=1, page_size=20, total=1),
    )

    assert response.model_dump(mode="json") == {
        "items": ["item"],
        "meta": {"page": 1, "page_size": 20, "total": 1},
    }


@pytest.mark.unit
def test_error_response_contract() -> None:
    response = ErrorResponse(
        error=ErrorDetail(
            code="ACCESS_DENIED",
            message="Denied.",
            details={},
            trace_id="00000000-0000-0000-0000-000000000001",
        )
    )

    assert set(response.model_dump(mode="json")) == {"error"}
    assert set(response.model_dump(mode="json")["error"]) == {"code", "message", "details", "trace_id"}
