from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = (len(ordered) - 1) * percent
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 3)


def distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "samples": len(values),
        "min": round(min(values), 3) if values else None,
        "mean": round(statistics.fmean(values), 3) if values else None,
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": round(max(values), 3) if values else None,
    }


def clone_bundle(bundle, suffix: str):
    payload = bundle.model_dump(mode="json")
    payload["case_id"] = f"{payload['case_id']}-{suffix}"
    payload["customer_id"] = f"{payload['customer_id']}-{suffix}"
    return type(bundle).model_validate(payload)


def deterministic_benchmark(bundle, iterations: int):
    from app.orchestration.pipeline import AssessmentPipeline

    pipeline = AssessmentPipeline()
    latencies: list[float] = []
    for index in range(iterations):
        sample = clone_bundle(bundle, f"DET-{index:04d}")
        started = time.perf_counter()
        pipeline.assess(sample)
        latencies.append((time.perf_counter() - started) * 1000)
    return distribution(latencies)


def cache_benchmark(bundle, iterations: int):
    from app.orchestration.pipeline import AssessmentPipeline

    pipeline = AssessmentPipeline()
    pipeline.assess(bundle)
    latencies: list[float] = []
    cache_flags: list[bool] = []
    for _ in range(iterations):
        started = time.perf_counter()
        result = pipeline.assess(bundle)
        latencies.append((time.perf_counter() - started) * 1000)
        cache_flags.append(result.cached)

    concurrent_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as executor:
        concurrent_results = list(executor.map(lambda _: pipeline.assess(bundle), range(iterations)))
    concurrent_seconds = time.perf_counter() - concurrent_started
    return {
        "sequential_latency_ms": distribution(latencies),
        "cache_hit_rate": sum(cache_flags) / len(cache_flags),
        "concurrent_workers": 10,
        "concurrent_requests": iterations,
        "concurrent_throughput_requests_per_second": round(iterations / concurrent_seconds, 3),
        "concurrent_all_cached": all(item.cached for item in concurrent_results),
    }


def live_case(
    client,
    case_name: str,
    bundle,
    repeats: int,
    expected_decision: str | None,
    auditor_attempts: int,
):
    from app.agents.chief_reviewer import ChiefCreditReviewerAgent
    from app.agents.document_auditor import DocumentAuditorAgent
    from app.orchestration.pipeline import AssessmentPipeline

    pipeline = AssessmentPipeline(
        auditor=DocumentAuditorAgent(client, max_attempts=auditor_attempts),
        reviewer=ChiefCreditReviewerAgent(client),
    )
    rows: list[dict] = []
    for index in range(repeats):
        sample = clone_bundle(bundle, f"LIVE-{case_name.upper()}-{index:02d}")
        start_metric = len(client.call_history)
        started = time.perf_counter()
        try:
            execution = pipeline.assess(sample)
            elapsed_ms = (time.perf_counter() - started) * 1000
            calls = client.call_history[start_metric:]
            report = execution.report
            row = {
                "run": index + 1,
                "success": True,
                "total_latency_ms": round(elapsed_ms, 3),
                "document_auditor_ms": round(
                    sum(item.latency_ms for item in calls if item.response_model == "AuditorReport"), 3
                ),
                "chief_reviewer_ms": round(
                    sum(item.latency_ms for item in calls if item.response_model == "ChiefReviewDraft"), 3
                ),
                "non_llm_overhead_ms": round(elapsed_ms - sum(item.latency_ms for item in calls), 3),
                "llm_calls": len(calls),
                "auditor_attempts": sum(item.response_model == "AuditorReport" for item in calls),
                "retry_count": max(
                    0, sum(item.response_model == "AuditorReport" for item in calls) - 1
                ),
                "prompt_tokens": sum(item.prompt_tokens or 0 for item in calls),
                "completion_tokens": sum(item.completion_tokens or 0 for item in calls),
                "total_tokens": sum(item.total_tokens or 0 for item in calls),
                "processing_status": report.processing_status.value,
                "decision": report.decision_recommendation.value
                if report.decision_recommendation
                else None,
                "decision_correct": expected_decision is None
                or (
                    report.decision_recommendation is not None
                    and report.decision_recommendation.value == expected_decision
                ),
                "issue_count": len(report.all_issues),
                "issue_categories": sorted({issue.category.value for issue in report.all_issues}),
                "critical_issue_categories": sorted(
                    {
                        issue.category.value
                        for issue in report.all_issues
                        if issue.severity.value == "critical"
                    }
                ),
            }
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            calls = client.call_history[start_metric:]
            row = {
                "run": index + 1,
                "success": False,
                "total_latency_ms": round(elapsed_ms, 3),
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
                "llm_calls": len(calls),
                "retry_count": max(
                    0, sum(item.response_model == "AuditorReport" for item in calls) - 1
                ),
                "total_tokens": sum(item.total_tokens or 0 for item in calls),
            }
        rows.append(row)
        print(
            json.dumps(
                {
                    "case": case_name,
                    "run": index + 1,
                    "success": row["success"],
                    "latency_seconds": round(row["total_latency_ms"] / 1000, 3),
                    "decision": row.get("decision"),
                    "calls": row.get("llm_calls"),
                    "tokens": row.get("total_tokens"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    successful = [row for row in rows if row["success"]]
    totals = [row["total_latency_ms"] for row in successful]
    auditor = [row["document_auditor_ms"] for row in successful]
    chief = [row["chief_reviewer_ms"] for row in successful]
    tokens = [float(row["total_tokens"]) for row in successful]
    expected_categories = {
        "HARD_STOP",
        "CIC_RED_FLAG",
        "FINANCIAL_LOGIC_FAIL",
        "CROSS_CHECK_MISMATCH",
        "MINOR_DISCREPANCY",
    }
    category_recalls = []
    if case_name == "multi_issue":
        category_recalls = [
            len(set(row["issue_categories"]) & expected_categories) / len(expected_categories)
            for row in successful
        ]
    return {
        "input_pages": bundle.document_manifest.total_pages,
        "input_characters": sum(len(page.ocr_text) for page in bundle.ocr_pages),
        "runs_requested": repeats,
        "success_rate": len(successful) / repeats,
        "decision_accuracy": (
            sum(bool(row["decision_correct"]) for row in successful) / len(successful)
            if successful
            else None
        ),
        "latency_ms": distribution(totals),
        "document_auditor_latency_ms": distribution(auditor),
        "chief_reviewer_latency_ms": distribution(chief),
        "total_tokens": distribution(tokens),
        "first_attempt_structured_success_rate": (
            sum(row["auditor_attempts"] == 1 for row in successful) / len(successful)
            if successful
            else None
        ),
        "overall_structured_success_rate": len(successful) / repeats,
        "mean_multi_issue_category_recall": (
            round(statistics.fmean(category_recalls), 4) if category_recalls else None
        ),
        "raw_runs": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark only the credit-assessment microservice")
    parser.add_argument("--live-repeats", type=int, default=3)
    parser.add_argument("--actual-repeats", type=int, default=1)
    parser.add_argument("--deterministic-iterations", type=int, default=100)
    parser.add_argument("--cache-iterations", type=int, default=100)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--auditor-attempts", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("artifacts/benchmark/benchmark-results.json"))
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    load_dotenv(project_root / ".env", override=True)

    from app.llm_client.glm_client import GLMStructuredClient
    from app.schemas.input_ocr_bundle import OCRBundle

    def load(relative: str):
        return OCRBundle.model_validate_json((project_root / relative).read_text(encoding="utf-8"))

    clean = load("tests/fixtures/clean_bundle.json")
    borderline = load("tests/fixtures/borderline_bundle.json")
    multi_issue = load("tests/fixtures/multi_issue_bundle.json")
    vinanova = load("artifacts/actual-input/vinanova.ocr-bundle.json")

    report = {
        "scope": "credit-assessment-agent microservice only; OCR and outer banking system excluded",
        "model": "GLM-5.2",
        "deterministic": {
            "clean_no_cache": deterministic_benchmark(clean, args.deterministic_iterations),
            "multi_issue_no_cache": deterministic_benchmark(
                multi_issue, args.deterministic_iterations
            ),
        },
        "cache": cache_benchmark(clean, args.cache_iterations),
        "live_glm": {},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    client = GLMStructuredClient(
        timeout_seconds=args.timeout_seconds,
        max_tokens=args.max_tokens,
    )
    try:
        report["live_glm"]["clean"] = live_case(
            client, "clean", clean, args.live_repeats, "APPROVE", args.auditor_attempts
        )
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["live_glm"]["borderline"] = live_case(
            client,
            "borderline",
            borderline,
            args.live_repeats,
            "APPROVE_WITH_CONDITIONS",
            args.auditor_attempts,
        )
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["live_glm"]["multi_issue"] = live_case(
            client,
            "multi_issue",
            multi_issue,
            args.live_repeats,
            "REJECT",
            args.auditor_attempts,
        )
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["live_glm"]["vinanova_actual"] = live_case(
            client,
            "vinanova_actual",
            vinanova,
            args.actual_repeats,
            None,
            args.auditor_attempts,
        )
        report["all_llm_calls"] = [metric.to_dict() for metric in client.call_history]
    finally:
        client.close()

    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
