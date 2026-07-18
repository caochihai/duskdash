"""Export integration-ready JSON Schemas from the Pydantic V1 contracts."""

from __future__ import annotations

import json
from pathlib import Path

from credit_agent.models import (
    NON_NEGATIVE_DECIMAL_PATTERN,
    POSITIVE_DECIMAL_PATTERN,
    CreditAnalysisResultV1,
    CreditTaskInputV1,
    _credit_result_schema_metadata,
    _credit_task_schema_metadata,
)


def _set_string_branch_pattern(property_schema: dict, pattern: str) -> None:
    for branch in property_schema.get("anyOf", []):
        if branch.get("type") == "string":
            branch["pattern"] = pattern


def _annotate_input_schema(schema: dict) -> None:
    _credit_task_schema_metadata(schema)
    request = schema["$defs"]["CreditRequest"]["properties"]
    _set_string_branch_pattern(request["current_limit"], NON_NEGATIVE_DECIMAL_PATTERN)
    _set_string_branch_pattern(request["requested_limit"], POSITIVE_DECIMAL_PATTERN)


def _annotate_output_schema(schema: dict) -> None:
    _credit_result_schema_metadata(schema)


def build_contracts() -> dict[str, dict]:
    contracts = {
        "credit_task_input_v1.json": CreditTaskInputV1.model_json_schema(
            mode="validation"
        ),
        "credit_analysis_result_v1.json": CreditAnalysisResultV1.model_json_schema(
            mode="serialization"
        ),
    }
    _annotate_input_schema(contracts["credit_task_input_v1.json"])
    _annotate_output_schema(contracts["credit_analysis_result_v1.json"])
    return contracts


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "schemas"
    target.mkdir(exist_ok=True)
    contracts = build_contracts()
    for filename, schema in contracts.items():
        (target / filename).write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Exported {len(contracts)} schemas to {target}")


if __name__ == "__main__":
    main()
