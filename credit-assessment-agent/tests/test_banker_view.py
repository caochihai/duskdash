from app.engine.input_metadata_guard import remove_dataset_marker_false_positives
from app.orchestration.pipeline import AssessmentPipeline
from app.schemas.common import Evidence, Issue, IssueCategory, IssueLocation, Severity


def test_banker_view_exposes_exact_source_and_next_step(multi_issue_bundle):
    report = AssessmentPipeline().assess(multi_issue_bundle).report
    view = report.banker_view
    assert view is not None
    assert view.total_findings == 5
    first = next(item for item in view.findings if item.finding_id == "ISS-001")
    assert first.sources[0].document_id == "DOC-LOAN-FILE"
    assert first.sources[0].page_number == 1
    assert first.sources[0].source_filename == "DOC-LOAN-FILE"
    assert "tranh chấp" in first.sources[0].source_excerpt.lower()
    assert first.why_it_is_an_issue
    assert first.business_impact
    assert "chạy lại assessment" in first.next_step_after_fix.lower()
    assert view.one_time_customer_request_list == []
    assert view.action_plan.manual_policy_review_required is True
    assert first.recommended_action_ids


def test_dataset_marker_repeated_across_bundle_is_not_customer_fraud(clean_bundle):
    payload = clean_bundle.model_dump(mode="json")
    marker = "Mã số giấy tờ, số sổ, QR, mã tra cứu, con dấu và cơ quan phát hành đều là giả lập."
    for page in payload["ocr_pages"]:
        page["ocr_text"] += "\n" + marker
    from app.schemas.input_ocr_bundle import OCRBundle

    bundle = OCRBundle.model_validate(payload)
    issue = Issue(
        issue_id="FAKE-001",
        category=IssueCategory.HARD_STOP,
        severity=Severity.CRITICAL,
        location=IssueLocation(document_id="DOC-CLEAN", page_number=1),
        description="Tài liệu có ghi chú con dấu và cơ quan phát hành đều là giả lập.",
        evidence=[
            Evidence(source="DOC-CLEAN#page=1", value="đều là giả lập")
        ],
        requires_customer_action=True,
        suggested_customer_action="Cung cấp bản thật.",
    )
    assert remove_dataset_marker_false_positives(bundle, [issue]) == []


def test_specific_forgery_evidence_is_not_removed_by_dataset_guard(clean_bundle):
    payload = clean_bundle.model_dump(mode="json")
    marker = "Mã số giấy tờ, số sổ, QR, mã tra cứu, con dấu và cơ quan phát hành đều là giả lập."
    for page in payload["ocr_pages"]:
        page["ocr_text"] += "\n" + marker
    from app.schemas.input_ocr_bundle import OCRBundle

    bundle = OCRBundle.model_validate(payload)
    issue = Issue(
        issue_id="FORGERY-001",
        category=IssueCategory.HARD_STOP,
        severity=Severity.CRITICAL,
        location=IssueLocation(document_id="DOC-CLEAN", page_number=1),
        description="Nghị quyết nghi giả mạo: chữ ký bị phủ nhận và có hai mẫu dấu khác nhau.",
        evidence=[Evidence(source="DOC-CLEAN#page=1", value="chữ ký")],
        requires_customer_action=True,
        suggested_customer_action="Đối chiếu bản gốc.",
    )
    assert remove_dataset_marker_false_positives(bundle, [issue]) == [issue]
