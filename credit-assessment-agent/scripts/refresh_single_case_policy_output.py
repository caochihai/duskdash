from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.issue_taxonomy_guard import normalize_issue_taxonomy
from app.reporting.banker_view import build_banker_view, enrich_issues_with_source_metadata
from app.schemas.input_extracted_bundle import ExtractedCaseBundle
from app.schemas.output_report import AssessmentReport
from scripts.run_single_extracted_case import _markdown


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh deterministic guards/action plan without another LLM call"
    )
    parser.add_argument("input_file", type=Path)
    parser.add_argument("assessment_json", type=Path)
    args = parser.parse_args()

    bundle = ExtractedCaseBundle.model_validate_json(args.input_file.read_text(encoding="utf-8"))
    artifact = json.loads(args.assessment_json.read_text(encoding="utf-8"))
    report = AssessmentReport.model_validate(artifact["execution"]["report"])
    guarded_issues = normalize_issue_taxonomy(report.all_issues)
    enriched_issues = enrich_issues_with_source_metadata(bundle, guarded_issues)
    banker_view = build_banker_view(
        bundle=bundle,
        issues=enriched_issues,
        decision=report.decision_recommendation,
        decision_summary=report.decision_summary,
        customer_requests=report.consolidated_customer_requests,
    )
    refreshed = report.model_copy(
        update={"all_issues": enriched_issues, "banker_view": banker_view}
    )
    artifact["execution"]["report"] = refreshed.model_dump(mode="json")
    args.assessment_json.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    args.assessment_json.with_suffix(".md").write_text(_markdown(artifact), encoding="utf-8")
    print(
        json.dumps(
            {
                "assessment": str(args.assessment_json),
                "findings": banker_view.total_findings,
                "next_actions": len(banker_view.action_plan.next_actions),
                "manual_policy_review_required": (
                    banker_view.action_plan.manual_policy_review_required
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
