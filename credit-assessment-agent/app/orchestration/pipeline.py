from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import Field

from app.agents.chief_reviewer import ChiefCreditReviewerAgent
from app.agents.document_auditor import AGENT_PROMPT_VERSION, DocumentAuditorAgent
from app.engine.completeness_gate import evaluate_completeness
from app.engine.input_metadata_guard import remove_dataset_marker_false_positives
from app.engine.issue_taxonomy_guard import normalize_issue_taxonomy
from app.engine.metric_extractor import GroundedDTI, extract_grounded_dti
from app.engine.structured_crosscheck import detect_structured_cross_checks
from app.engine.policy_engine import POLICY_VERSION, evaluate_policy
from app.observability.tracing import log_event
from app.orchestration.cache import InMemoryAssessmentCache
from app.reporting.banker_view import (
    build_banker_view,
    enrich_issues_with_source_metadata,
    verified_issue_ids,
)
from app.schemas.auditor_report import AuditorReport, ReviewStatus
from app.schemas.common import ProcessingStatus, StrictModel
from app.schemas.input_ocr_bundle import OCRBundle
from app.schemas.output_report import (
    AssessmentReport,
    AuditTrace,
    KeyFinancialMetrics,
    MissingOrIncompleteDocument,
    MissingReason,
    OutputScanCompleteness,
)


class AssessmentExecution(StrictModel):
    job_id: str
    idempotency_key: str
    cached: bool
    report: AssessmentReport


class AssessmentPipeline:
    def __init__(
        self,
        auditor: DocumentAuditorAgent | None = None,
        reviewer: ChiefCreditReviewerAgent | None = None,
        cache: InMemoryAssessmentCache | None = None,
    ) -> None:
        self._auditor = auditor or DocumentAuditorAgent()
        self._reviewer = reviewer or ChiefCreditReviewerAgent()
        self._cache = cache or InMemoryAssessmentCache()

    def assess(self, bundle: OCRBundle) -> AssessmentExecution:
        key = build_idempotency_key(bundle)
        job_id = "job-" + key[:24]
        cached = self._cache.get(key)
        if cached is not None:
            log_event("idempotency_cache_hit", case_id=bundle.case_id, job_id=job_id)
            return AssessmentExecution(job_id=job_id, idempotency_key=key, cached=True, report=cached)

        run_id = str(uuid4())
        log_event("pipeline_started", case_id=bundle.case_id, run_id=run_id, agent_id="pipeline")
        audit = self._auditor.audit(bundle, run_id=run_id)
        grounded_dti = extract_grounded_dti(bundle)
        if grounded_dti is not None:
            audit = _apply_grounded_dti(audit, grounded_dti)
        source_issues = remove_dataset_marker_false_positives(bundle, audit.issues_found)
        source_issues.extend(detect_structured_cross_checks(bundle, source_issues))
        guarded_issues = normalize_issue_taxonomy(source_issues)
        guarded_issue_ids = {issue.issue_id for issue in guarded_issues}
        issue_pages: dict[tuple[str, int], list[str]] = {}
        for issue in guarded_issues:
            for evidence in issue.evidence:
                if "#page=" not in evidence.source:
                    continue
                document_id, page_text = evidence.source.rsplit("#page=", 1)
                if page_text.isdigit():
                    issue_pages.setdefault((document_id, int(page_text)), []).append(issue.issue_id)
        audit = audit.model_copy(
            update={
                "issues_found": enrich_issues_with_source_metadata(bundle, guarded_issues),
                "page_audit": [
                    page.model_copy(
                        update={
                            "issues_on_page": list(
                                dict.fromkeys(
                                    [
                                        *[
                                            issue_id
                                            for issue_id in page.issues_on_page
                                            if issue_id in guarded_issue_ids
                                        ],
                                        *issue_pages.get((page.document_id, page.page_number), []),
                                    ]
                                )
                            )
                        }
                    )
                    for page in audit.page_audit
                ],
            }
        )
        log_event(
            "agent_completed",
            case_id=bundle.case_id,
            run_id=run_id,
            agent_id="document-auditor-agent",
            issue_count=len(audit.issues_found),
        )

        gate = evaluate_completeness(audit)
        if not gate.passed:
            log_event(
                "completeness_gate_rejected",
                case_id=bundle.case_id,
                run_id=run_id,
                agent_id="completeness-gate",
                reasons=gate.reasons,
            )
            report = _build_incomplete_report(bundle, audit, run_id, gate.reasons)
        else:
            policy = evaluate_policy(
                audit,
                verified_issue_ids=verified_issue_ids(bundle, audit.issues_found),
                verified_metric_names=_verified_metric_names(bundle, grounded_dti),
                required_checklist_verified=_required_checklist_verified(bundle),
            )
            log_event(
                "policy_completed",
                case_id=bundle.case_id,
                run_id=run_id,
                agent_id="policy-engine",
                decision=policy.decision_candidate,
                protected_reject=policy.protected_reject,
            )
            review = self._reviewer.review(audit, policy)
            report = AssessmentReport(
                case_id=bundle.case_id,
                customer_id=bundle.customer_id,
                processing_status=ProcessingStatus.COMPLETE,
                scan_completeness=_output_scan(audit),
                decision_recommendation=policy.decision_candidate,
                decision_summary=review.decision_summary,
                key_financial_metrics=_key_metrics(
                    audit,
                    policy.recalculated_dti_percent,
                    policy.recalculated_dscr,
                    dti_decision_eligible=policy.dti_decision_eligible,
                    dscr_decision_eligible=policy.dscr_decision_eligible,
                    grounded_dti=grounded_dti,
                ),
                all_issues=audit.issues_found,
                missing_or_incomplete_documents=[],
                consolidated_customer_requests=review.consolidated_customer_requests,
                approval_conditions_if_applicable=review.approval_conditions,
                human_review_required=True,
                human_review_focus=review.human_review_focus,
                banker_view=build_banker_view(
                    bundle=bundle,
                    issues=audit.issues_found,
                    decision=policy.decision_candidate,
                    decision_summary=review.decision_summary,
                    customer_requests=review.consolidated_customer_requests,
                ),
                audit_trace=_audit_trace(run_id),
            )
            log_event(
                "agent_completed",
                case_id=bundle.case_id,
                run_id=run_id,
                agent_id="chief-credit-reviewer-agent",
                decision=report.decision_recommendation,
            )

        self._cache.put(key, job_id, report)
        log_event("pipeline_completed", case_id=bundle.case_id, run_id=run_id, job_id=job_id)
        return AssessmentExecution(job_id=job_id, idempotency_key=key, cached=False, report=report)

    def get_job(self, job_id: str) -> AssessmentReport | None:
        return self._cache.get_job(job_id)


def build_idempotency_key(bundle: OCRBundle) -> str:
    manifest_payload = [
        {
            "document_id": doc.document_id,
            "document_type": doc.document_type.value,
            "page_count": doc.page_count,
            "sha256": doc.sha256.lower(),
        }
        for doc in sorted(bundle.document_manifest.documents, key=lambda item: item.document_id)
    ]
    manifest_hash = hashlib.sha256(
        json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    material = "|".join(
        [bundle.case_id, bundle.customer_id, manifest_hash, AGENT_PROMPT_VERSION, POLICY_VERSION]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _build_incomplete_report(
    bundle: OCRBundle,
    audit: AuditorReport,
    run_id: str,
    reasons: list[str],
) -> AssessmentReport:
    missing: list[MissingOrIncompleteDocument] = []
    for item in audit.documents_reviewed:
        if item.review_status == ReviewStatus.COMPLETE:
            continue
        if item.review_status == ReviewStatus.UNREADABLE:
            reason = MissingReason.UNREADABLE
        elif item.review_status == ReviewStatus.MISSING:
            reason = MissingReason.MISSING
        else:
            reason = MissingReason.INCOMPLETE_PAGES
        missing.append(
            MissingOrIncompleteDocument(
                document_type=item.document_type.value,
                reason=reason,
                impact="Không đủ dữ liệu kỹ thuật để hoàn tất bốn lớp thẩm định; cần xử lý lại OCR/input.",
            )
        )

    return AssessmentReport(
        case_id=bundle.case_id,
        customer_id=bundle.customer_id,
        processing_status=ProcessingStatus.INTERNAL_RETRY_REQUIRED,
        scan_completeness=_output_scan(audit),
        decision_recommendation=None,
        decision_summary="Pipeline dừng tại Completeness Gate: " + ", ".join(reasons),
        key_financial_metrics=_key_metrics(audit),
        all_issues=audit.issues_found,
        missing_or_incomplete_documents=missing,
        consolidated_customer_requests=[],
        approval_conditions_if_applicable=[],
        human_review_required=True,
        human_review_focus=["Khôi phục trang thiếu/không đọc được rồi chạy lại cùng hồ sơ."],
        banker_view=build_banker_view(
            bundle=bundle,
            issues=audit.issues_found,
            decision=None,
            decision_summary="Pipeline dừng tại Completeness Gate: " + ", ".join(reasons),
            customer_requests=[],
        ),
        audit_trace=_audit_trace(run_id),
    )


def _output_scan(audit: AuditorReport) -> OutputScanCompleteness:
    scan = audit.scan_completeness
    return OutputScanCompleteness(
        expected_pages=scan.expected_pages,
        reviewed_pages=scan.reviewed_pages,
        unreadable_pages=scan.unreadable_pages,
        missing_pages=scan.missing_pages,
        four_layers_completed=scan.four_layers_completed,
    )


def _key_metrics(
    audit: AuditorReport,
    recalculated_dti: float | None = None,
    recalculated_dscr: float | None = None,
    *,
    dti_decision_eligible: bool = False,
    dscr_decision_eligible: bool = False,
    grounded_dti: GroundedDTI | None = None,
) -> KeyFinancialMetrics:
    data = audit.extracted_data
    return KeyFinancialMetrics(
        declared_income=data.declared_monthly_income,
        recognized_income=data.recognized_monthly_income,
        dti_percent=recalculated_dti if recalculated_dti is not None else data.dti_percent,
        dscr=recalculated_dscr if recalculated_dscr is not None else data.dscr,
        cfads=data.cfads,
        highest_cic_group=data.highest_cic_group,
        maximum_dpd=data.maximum_dpd,
        recent_dpd=data.recent_dpd,
        dti_formula="(existing_monthly_debt_service + proposed_monthly_debt_service) / recognized_monthly_income * 100",
        dti_operands={
            key: value
            for key, value in {
                "existing_monthly_debt_service": data.existing_monthly_debt_service,
                "proposed_monthly_debt_service": data.proposed_monthly_debt_service,
                "recognized_monthly_income": data.recognized_monthly_income,
            }.items()
            if value is not None
        },
        dti_decision_eligible=dti_decision_eligible,
        dti_warning=(
            None
            if dti_decision_eligible or recalculated_dti is None
            else "Chưa có source cho đủ ba toán hạng; chỉ hiển thị tham khảo, không dùng để APPROVE/REJECT."
        ),
        dti_reported_percent=(grounded_dti.reported_percent if grounded_dti else None),
        dti_source=(
            f"{grounded_dti.source_filename}#page={grounded_dti.page_number}"
            if grounded_dti
            else None
        ),
        dti_source_excerpt=(grounded_dti.source_excerpt if grounded_dti else None),
        dti_reconciliation_status=("RECONCILED" if grounded_dti else "NOT_RECONCILED"),
        dscr_formula="cfads / total_debt_service",
        dscr_operands={
            key: value
            for key, value in {
                "cfads": data.cfads,
                "total_debt_service": data.total_debt_service,
            }.items()
            if value is not None
        },
        dscr_decision_eligible=dscr_decision_eligible,
        dscr_warning=(
            None
            if dscr_decision_eligible or recalculated_dscr is None
            else "Chưa có source cho đủ hai toán hạng; chỉ hiển thị tham khảo, không dùng để APPROVE/REJECT."
        ),
    )


def _verified_metric_names(bundle: OCRBundle, grounded_dti: GroundedDTI | None = None) -> set[str]:
    verified = {"dti"} if grounded_dti is not None else set()
    if bundle.policy_context is not None:
        return verified | set(bundle.policy_context.verified_metric_names)
    if _is_verified_fixture(bundle):
        return verified | {"dti", "dscr", "highest_cic_group"}
    return verified


def _required_checklist_verified(bundle: OCRBundle) -> bool:
    context = bundle.policy_context
    configured_bank_policy = bool(
        context is not None
        and context.policy_id
        and context.effective_from
        and context.action_rule_sections
    )
    return configured_bank_policy or _is_verified_fixture(bundle)


def _is_verified_fixture(bundle: OCRBundle) -> bool:
    return any(page.ocr_fields.get("_fixture_verified") is True for page in bundle.ocr_pages)


def _apply_grounded_dti(audit: AuditorReport, metric: GroundedDTI) -> AuditorReport:
    data = audit.extracted_data.model_copy(
        update={
            "recognized_monthly_income": metric.recognized_monthly_income,
            "existing_monthly_debt_service": metric.existing_monthly_debt_service,
            "proposed_monthly_debt_service": metric.proposed_monthly_debt_service,
            "dti_percent": metric.recalculated_percent,
        }
    )
    return audit.model_copy(update={"extracted_data": data})


def _audit_trace(run_id: str) -> AuditTrace:
    return AuditTrace(
        run_id=run_id,
        agent_prompt_version=AGENT_PROMPT_VERSION,
        policy_version=POLICY_VERSION,
        generated_at=datetime.now(UTC),
    )
