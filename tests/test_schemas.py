from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from credit_agent.agent import CreditAgent
from credit_agent.demo_tools import DemoCreditTools
from credit_agent.models import AgentConfig, CreditAnalysisResultV1, CreditTaskInputV1
from scripts.export_schemas import build_contracts


ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_checked_in_schemas_are_synchronized_with_runtime_models() -> None:
    for filename, generated in build_contracts().items():
        assert _json(ROOT / "schemas" / filename) == generated


def test_checked_in_input_schema_enforces_decimal_string_bounds() -> None:
    schema = _json(ROOT / "schemas" / "credit_task_input_v1.json")
    payload = _json(ROOT / "examples" / "credit_task.json")

    jsonschema.validate(payload, schema)

    invalid = copy.deepcopy(payload)
    invalid["credit_request"]["requested_limit"] = "-1"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_checked_in_output_schema_enforces_core_wire_conditionals() -> None:
    schema = _json(ROOT / "schemas" / "credit_analysis_result_v1.json")
    task = CreditTaskInputV1.model_validate(
        _json(ROOT / "examples" / "credit_task.json")
    )
    result = asyncio.run(
        CreditAgent(
            tools=DemoCreditTools(),
            config=AgentConfig(allow_placeholder_policy=True),
        ).run(task)
    )
    payload = result.model_dump(mode="json")

    jsonschema.validate(payload, schema)

    status_mismatch = copy.deepcopy(payload)
    status_mismatch["status"] = "NEEDS_INFO"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(status_mismatch, schema)

    invalid_coverage = copy.deepcopy(payload)
    invalid_coverage["data_quality"]["evidence_coverage"] = "2"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_coverage, schema)


def test_runtime_validator_remains_authoritative_for_evidence_integrity() -> None:
    task = CreditTaskInputV1.model_validate(
        _json(ROOT / "examples" / "credit_task.json")
    )
    result = asyncio.run(
        CreditAgent(
            tools=DemoCreditTools(),
            config=AgentConfig(allow_placeholder_policy=True),
        ).run(task)
    )
    payload = result.model_dump(mode="json")
    payload["recommendation"]["evidence_ids"].append("ev-does-not-exist")

    with pytest.raises(ValidationError, match="dangling evidence"):
        CreditAnalysisResultV1.model_validate(payload)

    missing_currency = result.model_dump(mode="json")
    missing_currency["recommendation"]["currency"] = None
    with pytest.raises(ValidationError, match="positive recommendation requires currency"):
        CreditAnalysisResultV1.model_validate(missing_currency)

    blocked_ready = result.model_dump(mode="json")
    blocked_ready["data_quality"]["overall_status"] = "BLOCKED"
    with pytest.raises(ValidationError, match="overall_status must agree"):
        CreditAnalysisResultV1.model_validate(blocked_ready)

    stale_ready = result.model_dump(mode="json")
    stale_ready["data_quality"]["freshness_status"] = "STALE"
    stale_ready["data_quality"]["datasets"]["financial_statements"][
        "freshness"
    ] = "STALE"
    with pytest.raises(ValidationError, match="freshness_status must agree"):
        CreditAnalysisResultV1.model_validate(stale_ready)

    blocked_dataset = result.model_dump(mode="json")
    blocked_dataset["data_quality"]["datasets"]["financial_statements"][
        "status"
    ] = "BLOCKED"
    with pytest.raises(ValidationError, match="overall_status must agree"):
        CreditAnalysisResultV1.model_validate(blocked_dataset)

    zero_coverage = result.model_dump(mode="json")
    zero_coverage["data_quality"]["evidence_coverage"] = "0"
    with pytest.raises(ValidationError, match="full canonical evidence coverage"):
        CreditAnalysisResultV1.model_validate(zero_coverage)

    invalid_pass = result.model_dump(mode="json")
    invalid_pass["recommendation"]["decision"] = "PASS_WITH_CONDITIONS"
    invalid_pass["conditions"] = [
        {
            "condition_code": "TEST_CONDITION",
            "description": "Synthetic contract test condition",
            "blocking": True,
            "stage": "BEFORE_APPROVAL_REVIEW",
            "evidence_ids": ["ev-policy"],
        }
    ]
    invalid_pass["missing_information"] = ["still missing"]
    with pytest.raises(ValidationError, match="PASS_WITH_CONDITIONS cannot"):
        CreditAnalysisResultV1.model_validate(invalid_pass)

    mixed_policy_status = result.model_dump(mode="json")
    expired = copy.deepcopy(mixed_policy_status["policy_citations"][0])
    expired["section"] = "expired.extra"
    expired["status"] = "EXPIRED"
    mixed_policy_status["policy_citations"].append(expired)
    with pytest.raises(ValidationError, match="every substantive policy citation"):
        CreditAnalysisResultV1.model_validate(mixed_policy_status)

    invalid_decline = result.model_dump(mode="json")
    invalid_decline["recommendation"]["decision"] = "NOT_RECOMMENDED"
    invalid_decline["recommendation"]["recommended_limit"] = None
    invalid_decline["recommendation"]["recommended_tenor_months"] = None
    invalid_decline["recommendation"]["currency"] = None
    invalid_decline["missing_information"] = ["unresolved evidence gap"]
    invalid_decline["data_quality"]["overall_status"] = "BLOCKED"
    for dataset in invalid_decline["data_quality"]["datasets"].values():
        dataset["status"] = "BLOCKED"
    with pytest.raises(ValidationError, match="NOT_RECOMMENDED requires"):
        CreditAnalysisResultV1.model_validate(invalid_decline)
