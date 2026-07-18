from __future__ import annotations

from pydantic import Field

from app.schemas.auditor_report import AuditorReport, ScanStatus
from app.schemas.common import StrictModel


class CompletenessGateResult(StrictModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)


def evaluate_completeness(report: AuditorReport) -> CompletenessGateResult:
    """Pure completeness gate. It never trusts the LLM confirmation by itself."""

    scan = report.scan_completeness
    reasons: list[str] = []
    ledger_keys = {(page.document_id, page.page_number) for page in report.page_audit}
    reviewed_keys = {
        (page.document_id, page.page_number)
        for page in report.page_audit
        if page.scan_status == ScanStatus.REVIEWED
    }

    if len(ledger_keys) != scan.expected_pages:
        reasons.append("PAGE_LEDGER_DOES_NOT_COVER_MANIFEST")
    if len(reviewed_keys) != scan.expected_pages or scan.reviewed_pages != scan.expected_pages:
        reasons.append("REVIEWED_PAGES_NOT_EQUAL_EXPECTED_PAGES")
    if scan.reviewed_documents != scan.expected_documents:
        reasons.append("REVIEWED_DOCUMENTS_NOT_EQUAL_EXPECTED_DOCUMENTS")
    if scan.unreadable_pages > 0:
        reasons.append("UNREADABLE_PAGES_PRESENT")
    if scan.missing_pages > 0:
        reasons.append("MISSING_PAGES_PRESENT")
    if not scan.four_layers_completed:
        reasons.append("FOUR_LAYERS_NOT_COMPLETED")
    if not report.scan_completeness_confirmation:
        reasons.append("AGENT_COMPLETENESS_NOT_CONFIRMED")

    return CompletenessGateResult(passed=not reasons, reasons=list(dict.fromkeys(reasons)))

