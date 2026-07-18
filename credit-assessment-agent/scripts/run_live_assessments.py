from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.chief_reviewer import ChiefCreditReviewerAgent
from app.agents.document_auditor import DocumentAuditorAgent
from app.llm_client.glm_client import GLMStructuredClient
from app.orchestration.pipeline import AssessmentPipeline
from app.schemas.input_ocr_bundle import OCRBundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Run actual OCR bundles through GLM assessment")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--auditor-attempts", type=int, default=1)
    args = parser.parse_args()

    load_dotenv(override=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(args.input_dir.glob("*.ocr-bundle.json"))
    # Keep the canonical batch outputs and ignore the earlier compatibility alias.
    files = [path for path in files if path.name != "vinanova.ocr-bundle.json"]
    if not files:
        raise SystemExit(f"No OCR bundles found in {args.input_dir}")

    client = GLMStructuredClient(timeout_seconds=args.timeout, max_tokens=args.max_tokens)
    summaries: list[dict[str, object]] = []
    try:
        for path in files:
            bundle = OCRBundle.model_validate_json(path.read_text(encoding="utf-8"))
            client.reset_metrics()
            pipeline = AssessmentPipeline(
                auditor=DocumentAuditorAgent(client, max_attempts=args.auditor_attempts),
                reviewer=ChiefCreditReviewerAgent(client),
            )
            started = perf_counter()
            result: dict[str, object]
            try:
                execution = pipeline.assess(bundle)
                elapsed_ms = round((perf_counter() - started) * 1000, 3)
                report = execution.report.model_dump(mode="json")
                result = {
                    "source_bundle": str(path),
                    "success": True,
                    "elapsed_ms": elapsed_ms,
                    "llm_calls": [metric.to_dict() for metric in client.call_history],
                    "execution": execution.model_dump(mode="json"),
                }
                summary = {
                    "case_id": bundle.case_id,
                    "customer_id": bundle.customer_id,
                    "success": True,
                    "elapsed_ms": elapsed_ms,
                    "decision": report["decision_recommendation"],
                    "processing_status": report["processing_status"],
                    "issue_count": len(report["all_issues"]),
                    "total_tokens": sum(metric.total_tokens or 0 for metric in client.call_history),
                }
            except Exception as exc:
                elapsed_ms = round((perf_counter() - started) * 1000, 3)
                result = {
                    "source_bundle": str(path),
                    "success": False,
                    "elapsed_ms": elapsed_ms,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "llm_calls": [metric.to_dict() for metric in client.call_history],
                }
                summary = {
                    "case_id": bundle.case_id,
                    "customer_id": bundle.customer_id,
                    "success": False,
                    "elapsed_ms": elapsed_ms,
                    "error_type": type(exc).__name__,
                    "total_tokens": sum(metric.total_tokens or 0 for metric in client.call_history),
                }

            output = args.output_dir / f"{path.stem}.assessment.json"
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            summaries.append(summary)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        client.close()

    summary_path = args.output_dir / "assessment-summary.json"
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "cases": len(summaries)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
