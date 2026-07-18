from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.output_report import AssessmentReport


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the latest grounded assessment batch")
    parser.add_argument("assessment_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    index: list[dict[str, object]] = []
    for source in sorted(args.assessment_dir.glob("*.assessment.json")):
        artifact = json.loads(source.read_text(encoding="utf-8"))
        if not artifact.get("success"):
            index.append(
                {
                    "source": str(source),
                    "success": False,
                    "error_type": artifact.get("error_type"),
                    "error": artifact.get("error"),
                }
            )
            continue
        report = AssessmentReport.model_validate(artifact["execution"]["report"])
        view = report.banker_view
        if view is None:
            raise ValueError(f"Missing banker_view: {source}")
        performance = {
            "elapsed_ms": artifact.get("elapsed_ms") or artifact.get("source_elapsed_ms"),
            "replay_elapsed_ms": artifact.get("replay_elapsed_ms"),
            "total_tokens": sum(call.get("total_tokens") or 0 for call in artifact.get("llm_calls", [])),
            "llm_call_count": len(artifact.get("llm_calls", [])),
            "failed_llm_calls": sum(not call.get("success", False) for call in artifact.get("llm_calls", [])),
            "calls": artifact.get("llm_calls", []),
        }
        payload = {
            "source_assessment": str(source),
            "case_id": report.case_id,
            "customer_id": report.customer_id,
            "processing_status": report.processing_status.value,
            "decision": report.decision_recommendation.value if report.decision_recommendation else None,
            "decision_use_status": "HUMAN_REVIEW_REQUIRED",
            "performance": performance,
            "key_financial_metrics": report.key_financial_metrics.model_dump(mode="json"),
            "banker_view": view.model_dump(mode="json"),
            "missing_or_incomplete_documents": [
                item.model_dump(mode="json") for item in report.missing_or_incomplete_documents
            ],
            "approval_conditions": [
                item.model_dump(mode="json") for item in report.approval_conditions_if_applicable
            ],
            "human_review_focus": report.human_review_focus,
            "workflow_after_resolution": [
                "Mở đúng file/trang và xác minh mọi finding chưa VERIFIED.",
                "Gửi khách hàng một danh sách yêu cầu hợp nhất; nhận và OCR lại tài liệu bổ sung.",
                "Nạp policy_context gồm checklist và policy version đã được ngân hàng phê duyệt.",
                "Chạy lại assessment; chỉ finding VERIFIED/RESOLVED mới được vào Policy Engine.",
                "Chuyên viên có thẩm quyền kiểm tra điều kiện và ra quyết định cuối cùng.",
            ],
        }
        stem = source.name.removesuffix(".assessment.json")
        json_path = args.output_dir / f"{stem}.grounded-banker-report.json"
        md_path = args.output_dir / f"{stem}.grounded-banker-report.md"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(_markdown(payload), encoding="utf-8")
        index.append(
            {
                "case_id": report.case_id,
                "customer_id": report.customer_id,
                "success": True,
                "decision": payload["decision"],
                "decision_use_status": payload["decision_use_status"],
                "can_submit_for_approval": view.can_submit_for_approval,
                "findings": view.total_findings,
                "verified_evidence_findings": view.verified_findings,
                "findings_needing_human_verification": view.findings_needing_human_verification,
                "elapsed_ms": performance["elapsed_ms"],
                "total_tokens": performance["total_tokens"],
                "checklist_status": view.required_document_checklist_status,
                "markdown_report": str(md_path),
                "json_report": str(json_path),
            }
        )

    index_path = args.output_dir / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"reports": len(index), "index": str(index_path)}, ensure_ascii=False))


def _markdown(payload: dict) -> str:
    view = payload["banker_view"]
    metrics = payload["key_financial_metrics"]
    performance = payload["performance"]
    elapsed = (performance["elapsed_ms"] or 0) / 1000
    lines = [
        f"# Báo cáo hồ sơ — {payload['customer_id']}",
        "",
        "## Kết luận vận hành",
        "",
        f"- Trạng thái xử lý: **{payload['processing_status']}**",
        f"- Đề xuất của microservice: **{payload['decision']}**",
        f"- Trạng thái sử dụng: **{payload['decision_use_status']}**",
        f"- Có thể trình phê duyệt ngay: **{'Có' if view['can_submit_for_approval'] else 'Không'}**",
        f"- Checklist bắt buộc: `{view['required_document_checklist_status']}`",
        "",
        view["headline"],
        "",
        "## Chỉ số tài chính và khả năng dùng ra quyết định",
        "",
        f"- DTI: `{metrics.get('dti_percent')}`; decision eligible: `{metrics.get('dti_decision_eligible')}`.",
        f"- DTI source: `{metrics.get('dti_source')}`; reconcile: `{metrics.get('dti_reconciliation_status')}`.",
        f"- DTI warning: `{metrics.get('dti_warning')}`.",
        f"- DSCR: `{metrics.get('dscr')}`; decision eligible: `{metrics.get('dscr_decision_eligible')}`.",
        "",
        "## Lỗi/thiếu và hướng xử lý",
        "",
        "| ID | Kiểm chứng | Loại | Mức | Lỗi/thiếu gì | File/trang và bằng chứng | Tại sao | Ảnh hưởng quyết định | Cần làm gì | Sau khi sửa |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for finding in view["findings"]:
        sources = "<br>".join(
            f"{_cell(source['source_filename'])} — trang {source['page_number']}<br>“{_cell(source['source_excerpt'])}”"
            for source in finding["sources"]
        )
        lines.append(
            "| "
            + " | ".join(
                _cell(item)
                for item in (
                    finding["finding_id"],
                    finding["grounding_status"],
                    finding["finding_type"],
                    finding["severity"],
                    finding["what_is_wrong"],
                    sources,
                    finding["why_it_is_an_issue"],
                    finding["decision_effect"],
                    finding["customer_action"] or finding["internal_action"],
                    finding["next_step_after_fix"],
                )
            )
            + " |"
        )
    lines.extend(["", "## Yêu cầu khách hàng — gửi một lần", ""])
    requests = view["one_time_customer_request_list"]
    lines.extend(f"- {item}" for item in requests) if requests else lines.append("- Chưa có.")
    lines.extend(["", "## Luồng sau khi sửa/bổ sung", ""])
    lines.extend(
        f"{index}. {item}" for index, item in enumerate(payload["workflow_after_resolution"], 1)
    )
    lines.extend(
        [
            "",
            "## Hiệu năng",
            "",
            f"- Thời gian: **{elapsed:.1f} giây**.",
            f"- Tổng token: **{performance['total_tokens']:,}**.",
            f"- LLM calls: **{performance['llm_call_count']}**, failed/retried: **{performance['failed_llm_calls']}**.",
        ]
    )
    return "\n".join(lines) + "\n"


def _cell(value: object) -> str:
    return str(value).replace("|", "/").replace("\r", " ").replace("\n", " ").strip()


if __name__ == "__main__":
    main()
