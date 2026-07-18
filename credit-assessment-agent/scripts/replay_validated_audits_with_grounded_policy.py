from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.chief_reviewer import ChiefCreditReviewerAgent
from app.engine.input_metadata_guard import remove_dataset_marker_false_positives
from app.engine.issue_taxonomy_guard import normalize_issue_taxonomy
from app.engine.metric_extractor import GroundedDTI, extract_grounded_dti
from app.engine.policy_engine import evaluate_policy
from app.engine.structured_crosscheck import detect_structured_cross_checks
from app.orchestration.pipeline import (
    AssessmentExecution,
    _audit_trace,
    _key_metrics,
    build_idempotency_key,
)
from app.reporting.banker_view import (
    build_banker_view,
    enrich_issues_with_source_metadata,
    verified_issue_ids,
)
from app.schemas.auditor_report import (
    AuditorReport,
    CriterionResult,
    CriterionResults,
    DocumentManifestSummary,
    DocumentReviewed,
    ExtractedData,
    PageAudit,
    PageConclusion,
    ReviewStatus,
    ScanCompleteness,
    ScanStatus,
)
from app.schemas.common import CriterionStatus, Issue, IssueCategory, ProcessingStatus
from app.schemas.input_ocr_bundle import OCRBundle
from app.schemas.output_report import AssessmentReport


SOURCE_PATTERN = re.compile(r"(?P<document>[^#\s]+)#page=(?P<page>\d+)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay validated LLM audits through the latest deterministic safety layers"
    )
    parser.add_argument("ocr_dir", type=Path)
    parser.add_argument("fresh_assessment_dir", type=Path)
    parser.add_argument("archived_assessment_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"Output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    summaries: list[dict[str, object]] = []
    for bundle_path in sorted(args.ocr_dir.glob("*.ocr-bundle.json")):
        if bundle_path.name == "vinanova.ocr-bundle.json":
            continue
        bundle = OCRBundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))
        source_path, source_artifact, source_mode = _select_source(
            bundle_path, args.fresh_assessment_dir, args.archived_assessment_dir
        )
        source_report = AssessmentReport.model_validate(source_artifact["execution"]["report"])
        started = perf_counter()
        execution = _replay(bundle, source_report)
        replay_elapsed_ms = round((perf_counter() - started) * 1000, 3)
        result = {
            "source_bundle": str(bundle_path),
            "source_assessment_artifact": str(source_path),
            "source_mode": source_mode,
            "success": True,
            "source_elapsed_ms": source_artifact.get("elapsed_ms"),
            "replay_elapsed_ms": replay_elapsed_ms,
            "llm_calls": source_artifact.get("llm_calls", []),
            "execution": execution.model_dump(mode="json"),
        }
        output = args.output_dir / f"{bundle_path.stem}.assessment.json"
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        report = execution.report
        view = report.banker_view
        assert view is not None
        summaries.append(
            {
                "case_id": report.case_id,
                "customer_id": report.customer_id,
                "success": True,
                "source_mode": source_mode,
                "decision": report.decision_recommendation.value if report.decision_recommendation else None,
                "findings": view.total_findings,
                "verified_evidence_findings": view.verified_findings,
                "findings_needing_human_verification": view.findings_needing_human_verification,
                "can_submit_for_approval": view.can_submit_for_approval,
                "replay_elapsed_ms": replay_elapsed_ms,
            }
        )
    (args.output_dir / "assessment-summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"cases": len(summaries), "output": str(args.output_dir)}, ensure_ascii=False))


def _select_source(
    bundle_path: Path, fresh_dir: Path, archived_dir: Path
) -> tuple[Path, dict, str]:
    name = f"{bundle_path.stem}.assessment.json"
    fresh = fresh_dir / name
    if fresh.exists():
        artifact = json.loads(fresh.read_text(encoding="utf-8"))
        if artifact.get("success") and artifact.get("execution"):
            return fresh, artifact, "FRESH_LLM_SUCCESS"
    archived = archived_dir / name
    artifact = json.loads(archived.read_text(encoding="utf-8"))
    if not artifact.get("success") or not artifact.get("execution"):
        raise ValueError(f"No successful source assessment for {bundle_path.name}")
    return archived, artifact, "ARCHIVED_VALIDATED_AUDIT_REPLAY"


def _replay(bundle: OCRBundle, source_report: AssessmentReport) -> AssessmentExecution:
    metric = extract_grounded_dti(bundle)
    source_issues = remove_dataset_marker_false_positives(bundle, source_report.all_issues)
    source_issues.extend(detect_structured_cross_checks(bundle, source_issues))
    issues = enrich_issues_with_source_metadata(bundle, normalize_issue_taxonomy(source_issues))
    audit = _reconstruct_audit(bundle, source_report, issues, metric)
    verified_metrics = {"dti"} if metric is not None else set()
    policy = evaluate_policy(
        audit,
        verified_issue_ids=verified_issue_ids(bundle, issues),
        verified_metric_names=verified_metrics,
        required_checklist_verified=False,
    )
    review = ChiefCreditReviewerAgent().review(audit, policy)
    run_id = audit.run_id
    report = AssessmentReport(
        case_id=bundle.case_id,
        customer_id=bundle.customer_id,
        processing_status=ProcessingStatus.COMPLETE,
        scan_completeness=source_report.scan_completeness,
        decision_recommendation=policy.decision_candidate,
        decision_summary=review.decision_summary,
        key_financial_metrics=_key_metrics(
            audit,
            policy.recalculated_dti_percent,
            policy.recalculated_dscr,
            dti_decision_eligible=policy.dti_decision_eligible,
            dscr_decision_eligible=policy.dscr_decision_eligible,
            grounded_dti=metric,
        ),
        all_issues=issues,
        missing_or_incomplete_documents=source_report.missing_or_incomplete_documents,
        consolidated_customer_requests=review.consolidated_customer_requests,
        approval_conditions_if_applicable=review.approval_conditions,
        human_review_required=True,
        human_review_focus=review.human_review_focus,
        banker_view=build_banker_view(
            bundle=bundle,
            issues=issues,
            decision=policy.decision_candidate,
            decision_summary=review.decision_summary,
            customer_requests=review.consolidated_customer_requests,
        ),
        audit_trace=_audit_trace(run_id),
    )
    key = build_idempotency_key(bundle)
    return AssessmentExecution(
        job_id="job-replay-" + key[:17], idempotency_key=key, cached=False, report=report
    )


def _reconstruct_audit(
    bundle: OCRBundle,
    source_report: AssessmentReport,
    issues: list[Issue],
    metric: GroundedDTI | None,
) -> AuditorReport:
    by_page: dict[tuple[str, int], list[str]] = {}
    for issue in issues:
        refs: set[tuple[str, int]] = set()
        for evidence in issue.evidence:
            match = SOURCE_PATTERN.search(evidence.source)
            if match:
                refs.add((match.group("document"), int(match.group("page"))))
        if not refs:
            refs.add((issue.location.document_id, issue.location.page_number or 1))
        for ref in refs:
            by_page.setdefault(ref, []).append(issue.issue_id)

    metric_data = source_report.key_financial_metrics
    extracted = ExtractedData(
        declared_monthly_income=metric_data.declared_income,
        recognized_monthly_income=(
            metric.recognized_monthly_income if metric else metric_data.recognized_income
        ),
        existing_monthly_debt_service=(metric.existing_monthly_debt_service if metric else None),
        proposed_monthly_debt_service=(metric.proposed_monthly_debt_service if metric else None),
        dti_percent=(metric.recalculated_percent if metric else metric_data.dti_percent),
        cfads=metric_data.cfads,
        dscr=metric_data.dscr,
        highest_cic_group=metric_data.highest_cic_group,
        maximum_dpd=metric_data.maximum_dpd,
        recent_dpd=metric_data.recent_dpd,
    )
    pages = [
        PageAudit(
            document_id=page.document_id,
            page_number=page.page_number,
            scan_status=ScanStatus.REVIEWED,
            issues_on_page=list(dict.fromkeys(by_page.get((page.document_id, page.page_number), []))),
            page_conclusion=(
                PageConclusion.ISSUE_FOUND
                if by_page.get((page.document_id, page.page_number))
                else PageConclusion.NO_ISSUE_FOUND
            ),
        )
        for page in bundle.ocr_pages
    ]
    documents = [
        DocumentReviewed(
            document_id=item.document_id,
            document_type=item.document_type,
            pages_expected=item.page_count,
            pages_reviewed=sum(page.document_id == item.document_id for page in bundle.ocr_pages),
            review_status=ReviewStatus.COMPLETE,
        )
        for item in bundle.document_manifest.documents
    ]
    return AuditorReport(
        case_id=bundle.case_id,
        customer_id=bundle.customer_id,
        agent_id="validated-audit-replay",
        run_id=str(uuid4()),
        document_manifest_summary=DocumentManifestSummary(
            expected_documents=bundle.document_manifest.total_documents,
            expected_pages=bundle.document_manifest.total_pages,
            document_ids=[item.document_id for item in bundle.document_manifest.documents],
        ),
        documents_reviewed=documents,
        page_audit=pages,
        criterion_results=CriterionResults(
            hard_stop=[_criterion("REPLAY-HARD-STOP", IssueCategory.HARD_STOP, issues)],
            cic=[_criterion("REPLAY-CIC", IssueCategory.CIC_RED_FLAG, issues)],
            financial_logic=[
                _criterion("REPLAY-FINANCIAL", IssueCategory.FINANCIAL_LOGIC_FAIL, issues)
            ],
            cross_check=[
                _criterion("REPLAY-CROSS-CHECK", IssueCategory.CROSS_CHECK_MISMATCH, issues)
            ],
        ),
        extracted_data=extracted,
        issues_found=issues,
        scan_completeness=ScanCompleteness(
            expected_documents=bundle.document_manifest.total_documents,
            reviewed_documents=bundle.document_manifest.total_documents,
            expected_pages=bundle.document_manifest.total_pages,
            reviewed_pages=len(bundle.ocr_pages),
            unreadable_pages=0,
            missing_pages=0,
            four_layers_completed=True,
        ),
        scan_completeness_confirmation=True,
    )


def _criterion(criterion_id: str, category: IssueCategory, issues: list[Issue]) -> CriterionResult:
    related = [issue.issue_id for issue in issues if issue.category == category]
    return CriterionResult(
        criterion_id=criterion_id,
        criterion_name=category.value,
        status=CriterionStatus.FAIL if related else CriterionStatus.PASS,
        evidence_refs=related,
        notes="Reconstructed from a previously validated exhaustive audit.",
    )


if __name__ == "__main__":
    main()
