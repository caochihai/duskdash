from __future__ import annotations

import asyncio
from typing import Any

from scripts.evaluate_mock_bank_package import evaluate_records


def _record(case_id: str, customer_type: str, label: str) -> dict[str, Any]:
    return {
        "credit_case": {
            "case_id": case_id,
            "customer_id": f"customer-{case_id}",
            "decision_label": label,
            "requested_limit_vnd": 1000000,
            "snapshot_at": "2026-06-30T23:59:59+07:00",
            "is_simulated": True,
        },
        "customer": {"customer_type": customer_type},
    }


def test_mock_package_evaluator_preserves_scope_and_fails_closed() -> None:
    report = asyncio.run(
        evaluate_records(
            [
                _record("CORP-001", "CORPORATE", "APPROVE"),
                _record("IND-001", "INDIVIDUAL", "APPROVE"),
            ]
        )
    )

    assert report["summary"]["corporate_records_in_scope"] == 1
    assert report["summary"]["individual_records_out_of_scope"] == 1
    assert report["summary"]["agent_decision_counts"] == {"NEEDS_INFO": 1}
    assert report["summary"]["fail_closed_passed"] is True
    assert report["summary"]["scope_protection_passed"] is True
    assert report["cases"][0]["missing_information"] == [
        "applicable active credit policy"
    ]
    assert report["cases"][1]["agent_run_performed"] is False
