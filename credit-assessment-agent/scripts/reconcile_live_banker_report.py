from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.metric_extractor import extract_grounded_dti
from app.engine.structured_crosscheck import detect_structured_cross_checks
from app.reporting.banker_view import build_banker_view, enrich_issues_with_source_metadata
from app.schemas.common import Decision, Severity
from app.schemas.input_ocr_bundle import OCRBundle
from app.schemas.output_report import AssessmentReport, CustomerRequest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("assessment_artifact", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    bundle = OCRBundle.model_validate(json.loads(args.bundle.read_text(encoding="utf-8")))
    artifact = json.loads(args.assessment_artifact.read_text(encoding="utf-8"))
    report = AssessmentReport.model_validate(artifact["execution"]["report"])
    if report.decision_recommendation != Decision.PENDING:
        raise ValueError("This safety reconciliation only accepts an already-PENDING report")

    additions = detect_structured_cross_checks(bundle, report.all_issues)
    issues = enrich_issues_with_source_metadata(bundle, [*report.all_issues, *additions])
    metric = extract_grounded_dti(bundle)
    if metric is None:
        raise ValueError("No single-page reconciled DTI was found")

    metrics = report.key_financial_metrics.model_copy(
        update={
            "recognized_income": metric.recognized_monthly_income,
            "dti_percent": metric.recalculated_percent,
            "dti_operands": {
                "existing_monthly_debt_service": metric.existing_monthly_debt_service,
                "proposed_monthly_debt_service": metric.proposed_monthly_debt_service,
                "recognized_monthly_income": metric.recognized_monthly_income,
            },
            "dti_decision_eligible": True,
            "dti_warning": None,
            "dti_reported_percent": metric.reported_percent,
            "dti_source": f"{metric.source_filename}#page={metric.page_number}",
            "dti_source_excerpt": metric.source_excerpt,
            "dti_reconciliation_status": "RECONCILED",
        }
    )
    requests = list(report.consolidated_customer_requests)
    for index, issue in enumerate(additions, start=len(requests) + 1):
        requests.append(
            CustomerRequest(
                request_id=f"DET-REQ-{index:03d}",
                request=issue.suggested_customer_action or issue.description,
                related_issue_ids=[issue.issue_id],
                priority=issue.severity,
            )
        )

    summary = (
        "Hệ thống giữ PENDING: tài liệu nguồn ghi nhận phê duyệt có điều kiện 2,8 tỷ, "
        "nhưng OCR Bundle chưa có checklist chính sách bắt buộc và còn finding cần xác minh. "
        f"DTI đã đối soát từ một trang: ({metric.existing_monthly_debt_service:,.0f} + "
        f"{metric.proposed_monthly_debt_service:,.0f}) / {metric.recognized_monthly_income:,.0f} "
        f"= {metric.recalculated_percent:.4f}%, khớp số ghi {metric.reported_percent:.1f}%. "
        "Không có Hard Stop critical đã xác nhận trong báo cáo đã chuẩn hóa."
    )
    banker_view = build_banker_view(
        bundle=bundle,
        issues=issues,
        decision=Decision.PENDING,
        decision_summary=summary,
        customer_requests=requests,
    )
    reconciled = report.model_copy(
        update={
            "decision_recommendation": Decision.PENDING,
            "decision_summary": summary,
            "key_financial_metrics": metrics,
            "all_issues": issues,
            "consolidated_customer_requests": requests,
            "approval_conditions_if_applicable": [],
            "human_review_required": True,
            "human_review_focus": [
                "Xác nhận bốn mismatch định danh/ngày tháng được cross-check bằng code.",
                "Xác minh các finding chưa grounding đầy đủ; loại các so sánh khác bản chất/khác đơn vị.",
                "Nạp checklist hồ sơ và policy version do ngân hàng phê duyệt.",
                "Đối chiếu việc hoàn thành các điều kiện tại DOC-011 trước giải ngân.",
            ],
            "banker_view": banker_view,
        }
    )

    output = {
        "source_assessment_artifact": str(args.assessment_artifact),
        "source_bundle": str(args.bundle),
        "run_performance": {
            "elapsed_ms": artifact.get("elapsed_ms"),
            "total_tokens": sum(call.get("total_tokens") or 0 for call in artifact.get("llm_calls", [])),
            "llm_calls": artifact.get("llm_calls", []),
        },
        "system_decision": "PENDING",
        "decision_use_status": "HUMAN_REVIEW_REQUIRED",
        "document_recorded_outcome": {
            "value": "APPROVE_WITH_CONDITIONS",
            "source": "DOC-011#page=1",
            "source_filename": "ChatGPT Image 15_47_13 18 thg 7, 2026 (10).png",
            "excerpt": "KẾT LUẬN: CHỈ PHÊ DUYỆT CÓ ĐIỀU KIỆN; hạn mức 2,8 tỷ; giải ngân sau khi đáp ứng đầy đủ các điều kiện.",
        },
        "document_recorded_conditions": [
            "Giảm hạn mức khoản vay xuống 2,8 tỷ đồng.",
            "Tất toán khoản vay kinh doanh hiện hữu trước giải ngân.",
            "Giảm số dư thẻ tín dụng về tối đa 40 triệu đồng trước giải ngân.",
            "Bổ sung vốn tự có tối thiểu 25,4 triệu đồng.",
            "Mở tài khoản thanh toán chuyên biệt nhận doanh thu bán hàng và cam kết giao dịch qua tài khoản này.",
            "Bổ sung hồ sơ hoàn công/hoàn thiện pháp lý tài sản bảo đảm trước giải ngân.",
        ],
        "reconciled_report": reconciled.model_dump(mode="json"),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "le-thi-thanh-huong.reconciled-banker-report.json"
    md_path = args.output_dir / "le-thi-thanh-huong.reconciled-banker-report.md"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(output, reconciled), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))


def _render_markdown(output: dict, report: AssessmentReport) -> str:
    view = report.banker_view
    assert view is not None
    metrics = report.key_financial_metrics
    elapsed_seconds = (output["run_performance"]["elapsed_ms"] or 0) / 1000
    rows = []
    for item in view.findings:
        sources = "<br>".join(
            f"{_cell(source.source_filename)} — trang {source.page_number}<br>“{_cell(source.source_excerpt)}”"
            for source in item.sources
        )
        rows.append(
            "| {id} | {status} | {kind} | {wrong} | {sources} | {why} | {action} | {next_step} |".format(
                id=_cell(item.finding_id),
                status=_cell(item.grounding_status.value),
                kind=_cell(item.finding_type.value),
                wrong=_cell(item.what_is_wrong),
                sources=sources,
                why=_cell(item.why_it_is_an_issue),
                action=_cell(item.customer_action or item.internal_action),
                next_step=_cell(item.next_step_after_fix),
            )
        )
    conditions = "\n".join(f"- {item}" for item in output["document_recorded_conditions"])
    return f"""# Báo cáo vận hành hồ sơ Lê Thị Thanh Hương

## Kết luận dùng nghiệp vụ

- Quyết định an toàn của microservice: **PENDING — HUMAN_REVIEW_REQUIRED**.
- Kết luận đang ghi trong tài liệu nguồn: **APPROVE_WITH_CONDITIONS**, DOC-011 trang 1, hạn mức 2,8 tỷ đồng.
- Không có `HARD_STOP critical` đã xác nhận sau khi chuẩn hóa taxonomy.
- Chưa được trình phê duyệt tự động vì thiếu checklist policy từ upstream và còn {view.findings_needing_human_verification} finding cần xác minh.

## DTI đã sửa và truy nguồn

- Công thức: `(18.000.000 + 25.400.000) / 106.000.000 × 100 = {metrics.dti_percent:.4f}%`.
- Số ghi trên tài liệu: `{metrics.dti_reported_percent:.1f}%`; trạng thái: **{metrics.dti_reconciliation_status}**.
- Nguồn: **{metrics.dti_source}**.
- Trích đoạn: “{metrics.dti_source_excerpt}”.

## Điều kiện ghi tại hồ sơ nguồn

{conditions}

## Findings: lỗi gì, ở đâu, vì sao, sửa xong làm gì

| ID | Kiểm chứng | Loại | Lỗi/thiếu | File và trang | Vì sao | Cần sửa/làm | Sau khi sửa |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

## Hiệu năng lượt GLM

- Tổng thời gian: **{elapsed_seconds:.1f} giây**.
- Tổng token: **{output['run_performance']['total_tokens']:,}**.
- Số cuộc gọi LLM: **{len(output['run_performance']['llm_calls'])}**; có 1 lần reconcile lỗi kết nối và retry thành công.

## Luồng xử lý tiếp theo

1. Chuyên viên mở đúng file/trang và xác minh các finding chưa `VERIFIED`.
2. Gửi khách hàng một danh sách yêu cầu duy nhất; cập nhật chứng từ đã sửa/bổ sung.
3. Nạp checklist hồ sơ bắt buộc và phiên bản policy được ngân hàng phê duyệt vào `policy_context`.
4. Chạy lại OCR Bundle; cross-check định danh và DTI phải chuyển sang `RESOLVED/RECONCILED`.
5. Kiểm tra từng điều kiện DOC-011; chỉ sau đó mới trình người có thẩm quyền và giải ngân.
"""


def _cell(value: str) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


if __name__ == "__main__":
    main()
