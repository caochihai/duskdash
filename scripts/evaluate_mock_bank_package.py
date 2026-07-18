"""Evaluate the SME Credit Agent's safe compatibility with a mock-bank package.

The adapter intentionally maps only corporate records. It does not invent an
active policy, facility ledger, repayment history, audited financial statements,
or collateral valuation when the supplied package does not contain them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from credit_agent.agent import CreditAgent
from credit_agent.models import (
    AgentConfig,
    CreditPolicyResult,
    CreditTaskInputV1,
    RequestType,
    TaskType,
    ToolStatus,
)


REQUIRED_SCOPES = frozenset(
    {
        "customer:read",
        "credit:read",
        "financials:read",
        "policy:read",
        "transactions:read",
    }
)
LABEL_TO_CREDIT_DECISION = {
    "APPROVE": "READY_FOR_APPROVAL_REVIEW",
    "CONDITIONAL_APPROVE": "PASS_WITH_CONDITIONS_OR_MANUAL_REVIEW",
    "REJECT_AND_ESCALATE": "NOT_RECOMMENDED_OR_MANUAL_REVIEW",
}
UNAVAILABLE_FIELDS = [
    "active versioned credit policy and policy thresholds",
    "facility-level approved limit, outstanding, utilization, and maturity",
    "repayment DPD, restructuring, and lookback coverage",
    "current/prior audited financial statements",
    "collateral valuation date and policy-eligible valuation status",
]


class PolicyUnavailableTools:
    """Minimal read-only adapter that proves policy absence stops the agent."""

    async def retrieve_credit_policy(
        self, task: CreditTaskInputV1
    ) -> CreditPolicyResult:
        return CreditPolicyResult(
            task_id=task.task_id,
            case_id=task.case_id,
            customer_id=task.customer_id,
            tool_name="retrieve_credit_policy",
            tool_run_id=f"mock-policy-{task.case_id}",
            status=ToolStatus.NO_DATA,
            source_system="mock-bank-package",
            source_reference=f"mock-6-credit-cases/{task.case_id}/policy",
            as_of_date=task.as_of_date,
            retrieved_at=datetime.now(timezone.utc),
            warnings=[
                "The package contains no active, versioned credit policy or threshold set."
            ],
        )


def _snapshot_date(record: dict[str, Any]) -> str:
    snapshot = record["credit_case"].get("snapshot_at")
    if not isinstance(snapshot, str):
        raise ValueError("credit_case.snapshot_at must be an ISO-8601 timestamp")
    return datetime.fromisoformat(snapshot.replace("Z", "+00:00")).date().isoformat()


def build_corporate_task(record: dict[str, Any]) -> CreditTaskInputV1:
    """Map only explicit corporate fields, documenting necessary task defaults."""

    credit_case = record["credit_case"]
    customer = record["customer"]
    if customer.get("customer_type") != "CORPORATE":
        raise ValueError("Only CORPORATE records are within this SME agent's scope")
    requested_limit = Decimal(str(credit_case["requested_limit_vnd"]))
    case_id = str(credit_case["case_id"])
    return CreditTaskInputV1(
        task_id=f"mock-bank-{case_id}",
        case_id=case_id,
        task_type=TaskType.CREDIT_LIMIT_REVIEW,
        customer_id=str(credit_case["customer_id"]),
        credit_request={
            "request_type": RequestType.LIMIT_REVIEW,
            "product_code": "SME_WORKING_CAPITAL",
            "current_limit": Decimal("0"),
            "requested_limit": requested_limit,
            "requested_tenor_months": 12,
            "currency": "VND",
            "purpose": "Evaluation mapping: source package does not provide product, tenor, or purpose.",
            "collateral_required": False,
        },
        as_of_date=_snapshot_date(record),
        permissions={"allowed_scopes": REQUIRED_SCOPES},
        plan_id="mock-bank-package-evaluation",
        plan_version="1",
    )


async def evaluate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    agent = CreditAgent(tools=PolicyUnavailableTools(), config=AgentConfig())
    case_reports: list[dict[str, Any]] = []
    elapsed_ms: list[float] = []

    for record in records:
        credit_case = record["credit_case"]
        customer = record["customer"]
        case_id = str(credit_case["case_id"])
        expected_label = str(credit_case["decision_label"])
        if customer.get("customer_type") != "CORPORATE":
            case_reports.append(
                {
                    "case_id": case_id,
                    "customer_type": customer.get("customer_type"),
                    "reference_label": expected_label,
                    "scope_status": "OUT_OF_SCOPE",
                    "agent_run_performed": False,
                    "reason": "The Credit Agent is an SME/corporate specialist; personal-credit cases require a separate agent and policy.",
                }
            )
            continue

        task = build_corporate_task(record)
        started = time.perf_counter()
        result = await agent.run(task)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        elapsed_ms.append(duration_ms)
        case_reports.append(
            {
                "case_id": case_id,
                "customer_type": "CORPORATE",
                "reference_label": expected_label,
                "reference_credit_decision_interpretation": LABEL_TO_CREDIT_DECISION.get(
                    expected_label, "UNMAPPED"
                ),
                "scope_status": "IN_SCOPE_BUT_SOURCE_INCOMPLETE",
                "agent_run_performed": True,
                "agent_status": result.status.value,
                "agent_decision": result.recommendation.decision.value,
                "missing_information": result.missing_information,
                "tool_call_count": result.tool_call_count,
                "runtime_ms": duration_ms,
                "label_comparison_assessable": False,
                "label_comparison_reason": "A labelled decision cannot be compared until authoritative policy and mandatory SME-credit source data are available.",
            }
        )

    in_scope_runs = [item for item in case_reports if item["agent_run_performed"]]
    decisions = Counter(item["agent_decision"] for item in in_scope_runs)
    return {
        "evaluation_version": "1.0",
        "evaluation_type": "deterministic dataset compatibility and fail-closed test",
        "source_dataset": {
            "name": "mock_6_credit_cases",
            "simulated_data_required": True,
            "record_count": len(records),
        },
        "mapping_assumptions": [
            "Only CORPORATE records are passed to the SME Credit Agent.",
            "The source has no product, tenor, or current-facility field; the task uses a clearly marked LIMIT_REVIEW mapping with product SME_WORKING_CAPITAL, 12 months, and current_limit=0 solely to validate the input boundary.",
            "No source label, recommended limit, AML/fraud outcome, or fabricated financial value is supplied to the agent as credit evidence.",
        ],
        "mandatory_source_fields_absent": UNAVAILABLE_FIELDS,
        "summary": {
            "records_received": len(records),
            "corporate_records_in_scope": len(in_scope_runs),
            "individual_records_out_of_scope": len(records) - len(in_scope_runs),
            "agent_decision_counts": dict(sorted(decisions.items())),
            "total_agent_tool_calls": sum(item["tool_call_count"] for item in in_scope_runs),
            "mean_agent_runtime_ms": (
                round(sum(elapsed_ms) / len(elapsed_ms), 2) if elapsed_ms else None
            ),
            "labelled_decision_accuracy_percent": None,
            "accuracy_not_assessable_reason": "The source lacks mandatory policy and SME-credit records; the correct behavior is fail-closed, not a fabricated approve/reject prediction.",
            "scope_protection_passed": all(
                not item["agent_run_performed"]
                for item in case_reports
                if item["scope_status"] == "OUT_OF_SCOPE"
            ),
            "fail_closed_passed": all(
                item["agent_decision"] == "NEEDS_INFO" for item in in_scope_runs
            ),
        },
        "cases": case_reports,
    }


def load_records(path: Path) -> list[dict[str, Any]]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError("Input JSON must be an array of case objects.")
    if not all(item.get("credit_case", {}).get("is_simulated") is True for item in parsed):
        raise ValueError("This evaluator accepts only records explicitly marked is_simulated=true.")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(evaluate_records(load_records(args.input)))
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
