from app.agents.document_auditor import DocumentAuditorAgent
from app.schemas.common import CriterionStatus


def test_no_early_termination_returns_all_five_issues(multi_issue_bundle):
    report = DocumentAuditorAgent().audit(multi_issue_bundle, run_id="run-test")

    assert [issue.issue_id for issue in report.issues_found] == [
        "ISS-001",
        "ISS-002",
        "ISS-003",
        "ISS-004",
        "ISS-005",
    ]
    assert len(report.page_audit) == 5
    assert all(page.issues_on_page for page in report.page_audit)
    assert report.scan_completeness_confirmation is True


def test_missing_page_becomes_unknown_not_pass(missing_page_bundle):
    report = DocumentAuditorAgent().audit(missing_page_bundle, run_id="run-test")
    groups = report.criterion_results
    statuses = [item.status for group in (groups.hard_stop, groups.cic, groups.financial_logic, groups.cross_check) for item in group]
    assert statuses == [CriterionStatus.UNKNOWN] * 4
    assert report.scan_completeness_confirmation is False

