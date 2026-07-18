from app.orchestration.pipeline import AssessmentPipeline
from app.schemas.common import Decision, ProcessingStatus


def test_three_required_decision_scenarios(clean_bundle, borderline_bundle, multi_issue_bundle):
    pipeline = AssessmentPipeline()
    assert pipeline.assess(clean_bundle).report.decision_recommendation == Decision.APPROVE
    assert (
        pipeline.assess(borderline_bundle).report.decision_recommendation
        == Decision.APPROVE_WITH_CONDITIONS
    )
    assert pipeline.assess(multi_issue_bundle).report.decision_recommendation == Decision.REJECT


def test_missing_page_stops_with_no_credit_decision(missing_page_bundle):
    result = AssessmentPipeline().assess(missing_page_bundle).report
    assert result.processing_status == ProcessingStatus.INTERNAL_RETRY_REQUIRED
    assert result.decision_recommendation is None
    assert result.missing_or_incomplete_documents[0].reason == "INCOMPLETE_PAGES"


def test_same_input_is_cached_with_identical_report(clean_bundle):
    pipeline = AssessmentPipeline()
    first = pipeline.assess(clean_bundle)
    second = pipeline.assess(clean_bundle)
    assert first.cached is False
    assert second.cached is True
    assert first.job_id == second.job_id
    assert first.report == second.report


def test_unreadable_is_technical_not_customer_issue(clean_bundle):
    payload = clean_bundle.model_dump(mode="json")
    payload["ocr_pages"][0]["page_quality_flag"] = "UNREADABLE"
    payload["ocr_pages"][0]["ocr_text"] = ""
    payload["ocr_pages"][0]["ocr_fields"] = {}
    from app.schemas.input_ocr_bundle import OCRBundle

    report = AssessmentPipeline().assess(OCRBundle.model_validate(payload)).report
    assert report.processing_status == ProcessingStatus.INTERNAL_RETRY_REQUIRED
    assert report.all_issues == []
    assert report.missing_or_incomplete_documents[0].reason == "UNREADABLE"


def test_deterministic_demo_never_approves_unverified_external_ocr(clean_bundle):
    payload = clean_bundle.model_dump(mode="json")
    payload["ocr_pages"][0]["ocr_fields"].pop("_fixture_verified")
    from app.schemas.input_ocr_bundle import OCRBundle

    report = AssessmentPipeline().assess(OCRBundle.model_validate(payload)).report
    assert report.processing_status == ProcessingStatus.INTERNAL_RETRY_REQUIRED
    assert report.decision_recommendation is None
