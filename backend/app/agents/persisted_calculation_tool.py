"""Credit-agent tool that exposes only persisted deterministic calculations."""

from __future__ import annotations

from collections.abc import Mapping

from app.agents.base import AgentInput, CalculationReference

_REFERENCE_FIELDS = frozenset(CalculationReference.model_fields)


class PersistedCalculationTool:
    """Adapt RLS-scoped calculation rows; never calculate values with an LLM."""

    async def calculate_for_analysis(
        self, request: AgentInput
    ) -> tuple[CalculationReference, ...]:
        raw = request.context.get("calculations", ())
        if not isinstance(raw, (list, tuple)):
            raise ValueError("calculations context must be a list")

        references: list[CalculationReference] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("each persisted calculation must be an object")
            references.append(
                CalculationReference.model_validate(
                    {key: value for key, value in item.items() if key in _REFERENCE_FIELDS}
                )
            )
        return tuple(references)

