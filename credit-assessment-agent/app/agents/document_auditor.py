from __future__ import annotations

from collections import defaultdict
from uuid import uuid4

import httpx
from pydantic import ValidationError

from app.agents.prompts import (
    DOCUMENT_AUDITOR_CHUNK_PROMPT,
    DOCUMENT_AUDITOR_RECONCILE_PROMPT,
    DOCUMENT_AUDITOR_SYSTEM_PROMPT,
)
from app.llm_client.anthropic_client import StructuredLLMClient
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
from app.schemas.common import CriterionStatus, Issue, IssueCategory, StrictModel
from app.schemas.input_ocr_bundle import OCRBundle, PageQualityFlag


AGENT_ID = "document-auditor-agent"
AGENT_PROMPT_VERSION = "document-auditor-1.0"


class AuditorValidationError(ValueError):
    pass


class ChunkPageSummary(StrictModel):
    document_id: str
    page_number: int
    source_filename: str | None = None
    summary: str


class ChunkAuditDraft(StrictModel):
    pages_reviewed: list[ChunkPageSummary]
    criterion_results: CriterionResults
    extracted_data: ExtractedData
    issues_found: list[Issue]


class ReconciledAuditDraft(StrictModel):
    criterion_results: CriterionResults
    extracted_data: ExtractedData
    issues_found: list[Issue]


class DocumentAuditorAgent:
    def __init__(
        self,
        client: StructuredLLMClient | None = None,
        *,
        max_attempts: int = 2,
        chunk_size: int = 4,
    ) -> None:
        self._client = client
        self._max_attempts = max_attempts
        self._chunk_size = chunk_size

    def audit(self, bundle: OCRBundle, *, run_id: str | None = None) -> AuditorReport:
        resolved_run_id = run_id or str(uuid4())
        if self._client is None:
            report = _deterministic_fixture_audit(bundle, resolved_run_id)
            self._validate_against_bundle(report, bundle)
            return report

        if len(bundle.ocr_pages) > self._chunk_size:
            report = self._audit_chunked(bundle, resolved_run_id)
            self._validate_against_bundle(report, bundle)
            return report

        errors: list[str] = []
        for attempt in range(1, self._max_attempts + 1):
            payload = {
                "ocr_bundle": bundle.model_dump(mode="json"),
                "agent_id": AGENT_ID,
                "run_id": resolved_run_id,
                "validation_feedback": errors[-1] if errors else None,
                "attempt": attempt,
            }
            try:
                report = self._client.complete_json(
                    system_prompt=DOCUMENT_AUDITOR_SYSTEM_PROMPT,
                    payload=payload,
                    response_model=AuditorReport,
                )
                self._validate_against_bundle(report, bundle)
                return report
            except (ValidationError, ValueError, httpx.HTTPError) as exc:
                errors.append(str(exc))
        raise AuditorValidationError("Document Auditor output failed validation: " + " | ".join(errors))

    def _audit_chunked(self, bundle: OCRBundle, run_id: str) -> AuditorReport:
        chunks: list[ChunkAuditDraft] = []
        pages = list(bundle.ocr_pages)
        for offset in range(0, len(pages), self._chunk_size):
            assigned = pages[offset : offset + self._chunk_size]
            expected = {(page.document_id, page.page_number) for page in assigned}
            draft = self._complete_with_retry(
                system_prompt=DOCUMENT_AUDITOR_CHUNK_PROMPT,
                payload={
                    "case_id": bundle.case_id,
                    "customer_id": bundle.customer_id,
                    "overall_manifest": bundle.document_manifest.model_dump(mode="json"),
                    "assigned_pages": [page.model_dump(mode="json") for page in assigned],
                },
                response_model=ChunkAuditDraft,
                label=f"chunk-{offset // self._chunk_size + 1}",
            )
            actual = {(page.document_id, page.page_number) for page in draft.pages_reviewed}
            if actual != expected:
                raise AuditorValidationError(
                    f"chunk page coverage mismatch; missing={sorted(expected - actual)}, "
                    f"extra={sorted(actual - expected)}"
                )
            for issue in draft.issues_found:
                location = (issue.location.document_id, issue.location.page_number)
                if issue.location.page_number is not None and location not in expected:
                    raise AuditorValidationError(f"chunk issue {issue.issue_id} points outside assigned pages")
            chunks.append(draft)

        reconciled = self._complete_with_retry(
            system_prompt=DOCUMENT_AUDITOR_RECONCILE_PROMPT,
            payload={
                "case_id": bundle.case_id,
                "customer_id": bundle.customer_id,
                "manifest": bundle.document_manifest.model_dump(mode="json"),
                "chunk_audits": [chunk.model_dump(mode="json") for chunk in chunks],
            },
            response_model=ReconciledAuditDraft,
            label="reconciliation",
        )
        return _build_chunked_report(bundle, run_id, reconciled)

    def _complete_with_retry(self, *, system_prompt: str, payload: dict, response_model, label: str):
        assert self._client is not None
        errors: list[str] = []
        for attempt in range(1, self._max_attempts + 1):
            attempt_payload = dict(payload)
            attempt_payload.update(
                {"attempt": attempt, "validation_feedback": errors[-1] if errors else None}
            )
            try:
                return self._client.complete_json(
                    system_prompt=system_prompt,
                    payload=attempt_payload,
                    response_model=response_model,
                )
            except (ValidationError, ValueError, httpx.HTTPError) as exc:
                errors.append(str(exc))
        raise AuditorValidationError(f"{label} failed validation: " + " | ".join(errors))

    @staticmethod
    def _validate_against_bundle(report: AuditorReport, bundle: OCRBundle) -> None:
        if report.case_id != bundle.case_id or report.customer_id != bundle.customer_id:
            raise AuditorValidationError("agent changed case_id or customer_id")
        manifest = bundle.document_manifest
        summary = report.document_manifest_summary
        if summary.expected_documents != manifest.total_documents:
            raise AuditorValidationError("expected_documents does not match manifest")
        if summary.expected_pages != manifest.total_pages:
            raise AuditorValidationError("expected_pages does not match manifest")

        expected_pages = {
            (doc.document_id, page_number)
            for doc in manifest.documents
            for page_number in range(1, doc.page_count + 1)
        }
        ledger_pages = {(page.document_id, page.page_number) for page in report.page_audit}
        if ledger_pages != expected_pages:
            missing = sorted(expected_pages - ledger_pages)
            extra = sorted(ledger_pages - expected_pages)
            raise AuditorValidationError(f"page coverage mismatch; missing={missing}, extra={extra}")

        for issue in report.issues_found:
            location = (issue.location.document_id, issue.location.page_number)
            if issue.location.page_number is not None and location not in expected_pages:
                raise AuditorValidationError(f"issue {issue.issue_id} points outside the manifest")


def _build_chunked_report(
    bundle: OCRBundle,
    run_id: str,
    reconciled: ReconciledAuditDraft,
) -> AuditorReport:
    issue_ids = [issue.issue_id for issue in reconciled.issues_found]
    if len(issue_ids) != len(set(issue_ids)):
        raise AuditorValidationError("reconciliation returned duplicate issue_id values")

    manifest = bundle.document_manifest
    supplied = {(page.document_id, page.page_number): page for page in bundle.ocr_pages}
    expected = {
        (doc.document_id, page_number)
        for doc in manifest.documents
        for page_number in range(1, doc.page_count + 1)
    }
    for issue in reconciled.issues_found:
        location = (issue.location.document_id, issue.location.page_number)
        if issue.location.page_number is not None and location not in expected:
            raise AuditorValidationError(f"reconciled issue {issue.issue_id} points outside the manifest")

    page_issue_ids: dict[tuple[str, int], list[str]] = defaultdict(list)
    for issue in reconciled.issues_found:
        if issue.location.page_number is not None:
            page_issue_ids[(issue.location.document_id, issue.location.page_number)].append(issue.issue_id)

    page_audit: list[PageAudit] = []
    documents_reviewed: list[DocumentReviewed] = []
    reviewed_pages = 0
    unreadable_pages = 0
    missing_pages = 0
    reviewed_documents = 0

    for doc in manifest.documents:
        doc_reviewed = 0
        doc_unreadable = 0
        doc_missing = 0
        for page_number in range(1, doc.page_count + 1):
            key = (doc.document_id, page_number)
            page = supplied.get(key)
            issues = page_issue_ids.get(key, [])
            if page is None:
                scan_status = ScanStatus.MISSING
                conclusion = PageConclusion.MISSING
                doc_missing += 1
                missing_pages += 1
            elif page.page_quality_flag in {PageQualityFlag.UNREADABLE, PageQualityFlag.BLANK}:
                scan_status = ScanStatus.UNREADABLE
                conclusion = PageConclusion.UNREADABLE
                doc_unreadable += 1
                unreadable_pages += 1
            else:
                scan_status = ScanStatus.REVIEWED
                conclusion = PageConclusion.ISSUE_FOUND if issues else PageConclusion.NO_ISSUE_FOUND
                doc_reviewed += 1
                reviewed_pages += 1
            page_audit.append(
                PageAudit(
                    document_id=doc.document_id,
                    page_number=page_number,
                    scan_status=scan_status,
                    issues_on_page=issues,
                    page_conclusion=conclusion,
                )
            )

        if doc_reviewed == doc.page_count:
            status = ReviewStatus.COMPLETE
            reviewed_documents += 1
        elif doc_unreadable and not doc_reviewed and not doc_missing:
            status = ReviewStatus.UNREADABLE
        elif doc_missing and not doc_reviewed and not doc_unreadable:
            status = ReviewStatus.MISSING
        else:
            status = ReviewStatus.PARTIAL
        documents_reviewed.append(
            DocumentReviewed(
                document_id=doc.document_id,
                document_type=doc.document_type,
                pages_expected=doc.page_count,
                pages_reviewed=doc_reviewed,
                review_status=status,
            )
        )

    four_layers_completed = all(
        (
            reconciled.criterion_results.hard_stop,
            reconciled.criterion_results.cic,
            reconciled.criterion_results.financial_logic,
            reconciled.criterion_results.cross_check,
        )
    )
    complete = (
        reviewed_pages == manifest.total_pages
        and reviewed_documents == manifest.total_documents
        and unreadable_pages == 0
        and missing_pages == 0
        and four_layers_completed
    )
    return AuditorReport(
        case_id=bundle.case_id,
        customer_id=bundle.customer_id,
        agent_id=AGENT_ID,
        run_id=run_id,
        document_manifest_summary=DocumentManifestSummary(
            expected_documents=manifest.total_documents,
            expected_pages=manifest.total_pages,
            document_ids=[doc.document_id for doc in manifest.documents],
        ),
        documents_reviewed=documents_reviewed,
        page_audit=page_audit,
        criterion_results=reconciled.criterion_results,
        extracted_data=reconciled.extracted_data,
        issues_found=reconciled.issues_found,
        scan_completeness=ScanCompleteness(
            expected_documents=manifest.total_documents,
            reviewed_documents=reviewed_documents,
            expected_pages=manifest.total_pages,
            reviewed_pages=reviewed_pages,
            unreadable_pages=unreadable_pages,
            missing_pages=missing_pages,
            four_layers_completed=four_layers_completed,
        ),
        scan_completeness_confirmation=complete,
    )


def _criterion(group: str, failed: bool, unknown: bool) -> CriterionResult:
    status = CriterionStatus.UNKNOWN if unknown else (CriterionStatus.FAIL if failed else CriterionStatus.PASS)
    return CriterionResult(
        criterion_id=f"{group}-coverage",
        criterion_name=f"Kiểm tra đầy đủ lớp {group}",
        status=status,
        evidence_refs=[],
        notes="Generated by deterministic demo backend",
    )


def _deterministic_fixture_audit(bundle: OCRBundle, run_id: str) -> AuditorReport:
    """Deterministic offline backend for tests and demos.

    It consumes optional `_issues` and `_metrics` values embedded by controlled
    fixtures. Production OCR text must be processed with the Anthropic backend.
    """

    issues: list[Issue] = []
    metrics: dict[str, object] = {}
    supplied_pages = {(page.document_id, page.page_number): page for page in bundle.ocr_pages}
    page_issue_ids: dict[tuple[str, int], list[str]] = defaultdict(list)

    # Deliberately exhaust every supplied page; there is no return inside this loop.
    for page in bundle.ocr_pages:
        raw_issues = page.ocr_fields.get("_issues", [])
        if isinstance(raw_issues, list):
            for raw_issue in raw_issues:
                if isinstance(raw_issue, dict):
                    issue = Issue.model_validate(raw_issue)
                    issues.append(issue)
                    page_issue_ids[(page.document_id, page.page_number)].append(issue.issue_id)
        raw_metrics = page.ocr_fields.get("_metrics", {})
        if isinstance(raw_metrics, dict):
            metrics.update(raw_metrics)

    if len({issue.issue_id for issue in issues}) != len(issues):
        raise AuditorValidationError("fixture contains duplicate issue_id values")

    page_audit: list[PageAudit] = []
    documents_reviewed: list[DocumentReviewed] = []
    reviewed_pages = 0
    unreadable_pages = 0
    missing_pages = 0
    reviewed_documents = 0

    for doc in bundle.document_manifest.documents:
        doc_reviewed = 0
        doc_unreadable = 0
        doc_missing = 0
        for page_number in range(1, doc.page_count + 1):
            key = (doc.document_id, page_number)
            page = supplied_pages.get(key)
            issue_ids = page_issue_ids.get(key, [])
            if page is None:
                scan_status = ScanStatus.MISSING
                conclusion = PageConclusion.MISSING
                doc_missing += 1
                missing_pages += 1
            elif page.page_quality_flag in {PageQualityFlag.UNREADABLE, PageQualityFlag.BLANK}:
                scan_status = ScanStatus.UNREADABLE
                conclusion = PageConclusion.UNREADABLE
                doc_unreadable += 1
                unreadable_pages += 1
            else:
                scan_status = ScanStatus.REVIEWED
                conclusion = PageConclusion.ISSUE_FOUND if issue_ids else PageConclusion.NO_ISSUE_FOUND
                doc_reviewed += 1
                reviewed_pages += 1
            page_audit.append(
                PageAudit(
                    document_id=doc.document_id,
                    page_number=page_number,
                    scan_status=scan_status,
                    issues_on_page=issue_ids,
                    page_conclusion=conclusion,
                )
            )

        if doc_reviewed == doc.page_count:
            status = ReviewStatus.COMPLETE
            reviewed_documents += 1
        elif doc_unreadable and not doc_reviewed and not doc_missing:
            status = ReviewStatus.UNREADABLE
        elif doc_missing and not doc_reviewed and not doc_unreadable:
            status = ReviewStatus.MISSING
        else:
            status = ReviewStatus.PARTIAL
        documents_reviewed.append(
            DocumentReviewed(
                document_id=doc.document_id,
                document_type=doc.document_type,
                pages_expected=doc.page_count,
                pages_reviewed=doc_reviewed,
                review_status=status,
            )
        )

    fixture_verified = all(
        page.ocr_fields.get("_fixture_verified") is True for page in bundle.ocr_pages
    )
    incomplete = missing_pages > 0 or unreadable_pages > 0 or not fixture_verified
    categories = {issue.category for issue in issues}
    criterion_results = CriterionResults(
        hard_stop=[_criterion("HARD_STOP", IssueCategory.HARD_STOP in categories, incomplete)],
        cic=[_criterion("CIC", IssueCategory.CIC_RED_FLAG in categories, incomplete)],
        financial_logic=[
            _criterion("FINANCIAL_LOGIC", IssueCategory.FINANCIAL_LOGIC_FAIL in categories, incomplete)
        ],
        cross_check=[
            _criterion("CROSS_CHECK", IssueCategory.CROSS_CHECK_MISMATCH in categories, incomplete)
        ],
    )
    four_layers_completed = not incomplete
    complete = (
        reviewed_pages == bundle.document_manifest.total_pages
        and reviewed_documents == bundle.document_manifest.total_documents
        and four_layers_completed
    )

    return AuditorReport(
        case_id=bundle.case_id,
        customer_id=bundle.customer_id,
        agent_id=AGENT_ID,
        run_id=run_id,
        document_manifest_summary=DocumentManifestSummary(
            expected_documents=bundle.document_manifest.total_documents,
            expected_pages=bundle.document_manifest.total_pages,
            document_ids=[doc.document_id for doc in bundle.document_manifest.documents],
        ),
        documents_reviewed=documents_reviewed,
        page_audit=page_audit,
        criterion_results=criterion_results,
        extracted_data=ExtractedData.model_validate(metrics),
        issues_found=issues,
        scan_completeness=ScanCompleteness(
            expected_documents=bundle.document_manifest.total_documents,
            reviewed_documents=reviewed_documents,
            expected_pages=bundle.document_manifest.total_pages,
            reviewed_pages=reviewed_pages,
            unreadable_pages=unreadable_pages,
            missing_pages=missing_pages,
            four_layers_completed=four_layers_completed,
        ),
        scan_completeness_confirmation=complete,
    )
