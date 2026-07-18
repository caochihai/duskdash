"""Persistence adapter for deterministic calculation records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from app.compat import UTC
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, execute_returning


class CalculationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_record(self, values: Mapping[str, Any]) -> Record:
        payload = dict(values)
        payload.setdefault("id", uuid4())
        payload.setdefault("calculated_at", datetime.now(UTC))
        payload.setdefault("result_payload", {})
        row = await execute_returning(
            self.session,
            """
            INSERT INTO credit.calculation_record (
                id, loan_application_id, analysis_case_id, calculation_type,
                calculation_version, inputs, formula, result_value,
                result_payload, unit, calculated_at, created_by_type,
                created_by_id
            ) VALUES (
                :id, :loan_application_id, :analysis_case_id,
                :calculation_type, :calculation_version, CAST(:inputs AS jsonb),
                :formula, :result_value, CAST(:result_payload AS jsonb), :unit,
                :calculated_at, :created_by_type, :created_by_id
            ) RETURNING *
            """,
            payload,
        )
        if row is None:
            raise RuntimeError("Calculation insert returned no row")
        return row

