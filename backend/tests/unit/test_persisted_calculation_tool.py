from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents.base import AgentInput
from app.agents.persisted_calculation_tool import PersistedCalculationTool


@pytest.mark.asyncio
async def test_tool_adapts_only_persisted_calculation_reference_fields() -> None:
    calculation_id = uuid4()
    result = await PersistedCalculationTool().calculate_for_analysis(
        AgentInput(
            task_id=uuid4(),
            analysis_case_id=uuid4(),
            customer_id=uuid4(),
            context={
                "calculations": [
                    {
                        "calculation_id": calculation_id,
                        "calculation_type": "AFFORDABILITY",
                        "calculation_version": "1.0",
                        "inputs": {"existing_obligations": "15000000.0000"},
                        "result_value": Decimal("1.20"),
                        "result_payload": {
                            "dti": "1.20",
                            "dscr": "0.83",
                            "net_disposable_income": "-2000000.0000",
                        },
                        "unit": "RATIO",
                        "formula": "metadata not exposed to the agent contract",
                    }
                ]
            },
        )
    )

    assert len(result) == 1
    assert result[0].calculation_id == calculation_id
    assert result[0].result_payload["dscr"] == "0.83"


@pytest.mark.asyncio
async def test_tool_rejects_non_list_or_non_object_context() -> None:
    base = {
        "task_id": uuid4(),
        "analysis_case_id": uuid4(),
        "customer_id": uuid4(),
    }
    with pytest.raises(ValueError, match="must be a list"):
        await PersistedCalculationTool().calculate_for_analysis(
            AgentInput(**base, context={"calculations": "not-a-list"})
        )
    with pytest.raises(ValueError, match="must be an object"):
        await PersistedCalculationTool().calculate_for_analysis(
            AgentInput(**base, context={"calculations": ["not-an-object"]})
        )
