from app.agents.document_auditor import DocumentAuditorAgent
from app.engine.issue_taxonomy_guard import (
    is_decision_eligible_hard_stop,
    normalize_issue_taxonomy,
)
from app.engine.metric_extractor import extract_grounded_dti
from app.engine.structured_crosscheck import detect_structured_cross_checks
from app.engine.policy_engine import evaluate_policy
from app.schemas.common import Decision, Evidence, Issue, IssueCategory, IssueLocation, Severity


def _issue(description: str, *, issue_id: str = "ISS-SAFE-001") -> Issue:
    return Issue(
        issue_id=issue_id,
        category=IssueCategory.HARD_STOP,
        severity=Severity.CRITICAL,
        location=IssueLocation(document_id="DOC-001", page_number=1),
        description=description,
        evidence=[Evidence(source="DOC-001#page=1", value=description)],
        requires_customer_action=True,
        suggested_customer_action="Bổ sung và cập nhật hồ sơ.",
    )


def test_remediable_capital_shortfall_is_not_a_hard_stop():
    original = _issue("Vốn tự có xác minh thấp hơn vốn tự có khai báo.")
    normalized = normalize_issue_taxonomy([original])[0]
    assert normalized.category == IssueCategory.FINANCIAL_LOGIC_FAIL
    assert normalized.severity == Severity.HIGH
    assert is_decision_eligible_hard_stop(normalized) is False


def test_pre_disbursement_legal_completion_is_a_condition_not_reject():
    original = _issue("Hoàn thiện pháp lý và giải chấp của người bán trước khi giải ngân.")
    normalized = normalize_issue_taxonomy([original])[0]
    assert normalized.category == IssueCategory.PRE_DISBURSEMENT_CONDITION
    assert normalized.severity == Severity.HIGH


def test_real_dispute_remains_a_protected_hard_stop():
    original = _issue("Tài sản bảo đảm đang có tranh chấp lối đi chưa giải quyết.")
    normalized = normalize_issue_taxonomy([original])[0]
    assert normalized.category == IssueCategory.HARD_STOP
    assert normalized.severity == Severity.CRITICAL
    assert is_decision_eligible_hard_stop(normalized) is True


def test_unverified_decision_inputs_force_pending(multi_issue_bundle):
    audit = DocumentAuditorAgent().audit(multi_issue_bundle, run_id="run-safe")
    result = evaluate_policy(
        audit,
        verified_issue_ids=set(),
        verified_metric_names=set(),
        required_checklist_verified=False,
    )
    assert result.decision_candidate == Decision.PENDING
    assert result.protected_reject is False
    assert "UNVERIFIED_DECISION_INPUT" in result.reasons
    assert "DTI_OPERANDS_NOT_VERIFIED" in result.decision_input_warnings
    assert "REQUIRED_DOCUMENT_CHECKLIST_NOT_PROVIDED" in result.decision_input_warnings


def test_verified_real_hard_stop_can_still_reject(multi_issue_bundle):
    audit = DocumentAuditorAgent().audit(multi_issue_bundle, run_id="run-safe")
    result = evaluate_policy(
        audit,
        verified_issue_ids={"ISS-001"},
        verified_metric_names=set(),
        required_checklist_verified=False,
    )
    assert result.decision_candidate == Decision.REJECT
    assert result.protected_reject is True


def test_dti_operands_are_reconciled_from_one_exact_page(clean_bundle):
    payload = clean_bundle.model_dump(mode="json")
    payload["ocr_pages"][0]["ocr_text"] = """TỔNG HỢP THẨM ĐỊNH
thu nhập chấp nhận:
106 triệu đồng/tháng
Nghĩa vụ sau tái cấu trúc:
18 triệu đồng/tháng
Khoản trả nợ mới dự kiến:
25,4 triệu đồng/tháng
DTI sau tái cấu trúc:
40,9%
"""
    from app.schemas.input_ocr_bundle import OCRBundle

    metric = extract_grounded_dti(OCRBundle.model_validate(payload))
    assert metric is not None
    assert metric.recognized_monthly_income == 106_000_000
    assert metric.existing_monthly_debt_service == 18_000_000
    assert metric.proposed_monthly_debt_service == 25_400_000
    assert metric.recalculated_percent == 40.9434
    assert metric.reported_percent == 40.9


def test_dti_is_not_grounded_when_reported_result_conflicts(clean_bundle):
    payload = clean_bundle.model_dump(mode="json")
    payload["ocr_pages"][0]["ocr_text"] = """thu nhập chấp nhận:
106 triệu đồng/tháng
Nghĩa vụ sau tái cấu trúc:
18 triệu đồng/tháng
Khoản trả nợ mới dự kiến:
25,4 triệu đồng/tháng
DTI sau tái cấu trúc:
99%
"""
    from app.schemas.input_ocr_bundle import OCRBundle

    assert extract_grounded_dti(OCRBundle.model_validate(payload)) is None


def test_structured_crosscheck_catches_identity_values_on_exact_pages(clean_bundle):
    payload = clean_bundle.model_dump(mode="json")
    payload["document_manifest"] = {
        "total_documents": 2,
        "total_pages": 2,
        "documents": [
            {
                "document_id": "DOC-A",
                "document_type": "CCCD",
                "page_count": 1,
                "sha256": "a" * 64,
                "source_filename": "cccd.png",
            },
            {
                "document_id": "DOC-B",
                "document_type": "DANG_KY_KINH_DOANH",
                "page_count": 1,
                "sha256": "b" * 64,
                "source_filename": "dang-ky.png",
            },
        ],
    }
    base = payload["ocr_pages"][0]
    payload["ocr_pages"] = [
        {
            **base,
            "document_id": "DOC-A",
            "ocr_text": "THÔNG TIN KHÁCH HÀNG\nNgày sinh\n12/08/1984\nSố CCCD\n079191234567",
        },
        {
            **base,
            "document_id": "DOC-B",
            "ocr_text": "THÔNG TIN HỘ KINH DOANH\nSinh ngày\n12/06/1984\nSố CCCD\n079091234567",
        },
    ]
    from app.schemas.input_ocr_bundle import OCRBundle

    issues = detect_structured_cross_checks(OCRBundle.model_validate(payload), [])
    by_id = {issue.issue_id: issue for issue in issues}
    assert set(by_id) == {"DET-CITIZEN_ID", "DET-DATE_OF_BIRTH"}
    assert [item.source for item in by_id["DET-CITIZEN_ID"].evidence] == [
        "DOC-A#page=1",
        "DOC-B#page=1",
    ]
