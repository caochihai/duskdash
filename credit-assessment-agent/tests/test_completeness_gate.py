from app.agents.document_auditor import DocumentAuditorAgent
from app.engine.completeness_gate import evaluate_completeness


def test_complete_bundle_passes(clean_bundle):
    report = DocumentAuditorAgent().audit(clean_bundle, run_id="run-test")
    assert evaluate_completeness(report).passed is True


def test_missing_page_fails_before_policy(missing_page_bundle):
    report = DocumentAuditorAgent().audit(missing_page_bundle, run_id="run-test")
    result = evaluate_completeness(report)
    assert result.passed is False
    assert "REVIEWED_PAGES_NOT_EQUAL_EXPECTED_PAGES" in result.reasons
    assert "MISSING_PAGES_PRESENT" in result.reasons

