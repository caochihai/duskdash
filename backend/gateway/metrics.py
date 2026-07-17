"""Deterministic comparison metrics for demo runs; never fabricate model results."""
from __future__ import annotations

import time

from common import rag


def single_agent_baseline(case: dict) -> dict:
    """Read-only baseline: no planner, A2A, or commit permission."""
    started = time.perf_counter()
    request = case["payload"]["request"]
    evidence = rag.search("credit", "DSCR hạn mức", k=2)
    return {
        "provider": "deterministic_fake",
        "mode": "single_agent_read_only",
        "case_id": case["case_id"],
        "structured_output_valid": True,
        "commit_permitted": False,
        "evidence_coverage": 1.0 if evidence else 0.0,
        "policy_citations": [rag.citation(hit) for hit in evidence],
        "request_amount": request["amount"],
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def multi_agent_metrics(case: dict) -> dict:
    events = case.get("events", [])
    return {"provider": "deterministic_fake", "mode": "multi_agent",
            "case_id": case["case_id"], "event_count": len(events),
            "completion": case.get("state") == "Completed"}
