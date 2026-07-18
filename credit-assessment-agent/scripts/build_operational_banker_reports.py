from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.input_metadata_guard import remove_dataset_marker_false_positives
from app.reporting.banker_view import build_banker_view
from app.schemas.common import Decision
from app.schemas.input_ocr_bundle import OCRBundle
from app.schemas.output_report import AssessmentReport, CustomerRequest


SOURCE_PATTERN = re.compile(r"(?P<document>DOC-[A-Z0-9-]+)(?::|#page=)(?P<page>\d+)?")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build banker-facing reports from final assessments")
    parser.add_argument("assessment_dir", type=Path)
    parser.add_argument("evaluation_dir", type=Path)
    parser.add_argument("ocr_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    index: list[dict[str, object]] = []
    for assessment_path in sorted(args.assessment_dir.glob("*.assessment.json")):
        artifact = json.loads(assessment_path.read_text(encoding="utf-8"))
        report = AssessmentReport.model_validate(artifact["execution"]["report"])
        bundle_path = _find_bundle(args.ocr_dir, assessment_path.name)
        bundle = OCRBundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))
        evaluation_path = args.evaluation_dir / f"{assessment_path.stem}.content-evaluation.json"
        evaluation_artifact = json.loads(evaluation_path.read_text(encoding="utf-8"))
        evaluation = evaluation_artifact["evaluation"]

        guarded_issues = remove_dataset_marker_false_positives(bundle, report.all_issues)
        requests = [CustomerRequest.model_validate(item) for item in artifact["execution"]["report"]["consolidated_customer_requests"]]
        view = build_banker_view(
            bundle=bundle,
            issues=guarded_issues,
            decision=report.decision_recommendation,
            decision_summary=report.decision_summary,
            customer_requests=requests,
        )
        decision_usable = bool(evaluation["decision_supported"]) and evaluation["verdict"] != "FAIL"
        payload = {
            "case_id": report.case_id,
            "customer_id": report.customer_id,
            "processing_status": report.processing_status.value,
            "agent_decision": report.decision_recommendation.value if report.decision_recommendation else None,
            "decision_use_status": (
                "HUMAN_REVIEW_REQUIRED" if decision_usable else "DO_NOT_USE_REASSESSMENT_REQUIRED"
            ),
            "independently_supported_decision": evaluation["independently_supported_decision"],
            "verification_verdict": evaluation["verdict"],
            "verification_score": evaluation["overall_score"],
            "banker_view": view.model_dump(mode="json"),
            "verification_checks": evaluation["evidence_checks"],
            "unsupported_or_contradicted_claims": evaluation["unsupported_or_contradicted_claims"],
            "missed_material_facts": evaluation["missed_material_facts"],
            "recommended_corrections": evaluation["recommended_corrections"],
            "workflow_after_customer_response": [
                "Nhận đủ tài liệu/giải trình theo one_time_customer_request_list.",
                "OCR lại đúng tài liệu mới và giữ nguyên tên file, số trang, hash.",
                "Chạy lại Document Auditor và Evidence Grounding Gate.",
                "Chỉ dùng finding VERIFIED; finding chưa xác minh không được kích hoạt quyết định tự động.",
                "Policy Engine tính lại quyết định; chuyên viên kiểm tra và quyết định cuối.",
            ],
        }
        report_stem = assessment_path.name.removesuffix(".assessment.json")
        output_json = args.output_dir / f"{report_stem}.banker-report.json"
        output_md = args.output_dir / f"{report_stem}.banker-report.md"
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        output_md.write_text(_markdown(payload), encoding="utf-8")
        index.append(
            {
                "case_id": report.case_id,
                "customer_id": report.customer_id,
                "agent_decision": payload["agent_decision"],
                "decision_use_status": payload["decision_use_status"],
                "verification_score": payload["verification_score"],
                "findings": view.total_findings,
                "verified_findings": view.verified_findings,
                "findings_needing_human_verification": view.findings_needing_human_verification,
                "markdown_report": str(output_md),
                "json_report": str(output_json),
            }
        )

    index_path = args.output_dir / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"reports": len(index), "index": str(index_path)}, ensure_ascii=False))


def _find_bundle(ocr_dir: Path, assessment_name: str) -> Path:
    base = assessment_name.removesuffix(".assessment.json")
    candidate = ocr_dir / f"{base}.json"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"OCR Bundle not found for {assessment_name}: {candidate}")


def _markdown(payload: dict) -> str:
    view = payload["banker_view"]
    lines = [
        f"# Phiếu rà soát hồ sơ — {payload['customer_id']}",
        "",
        f"- Trạng thái xử lý: **{payload['processing_status']}**",
        f"- Đề xuất của agent: **{payload['agent_decision']}**",
        f"- Trạng thái sử dụng: **{payload['decision_use_status']}**",
        f"- Kết luận kiểm chứng độc lập: **{payload['independently_supported_decision']}**",
        f"- Điểm kiểm chứng: **{payload['verification_score']}/10**",
        f"- Có thể trình phê duyệt ngay: **{'Có' if view['can_submit_for_approval'] else 'Không'}**",
        "",
        "## Kết luận sơ bộ",
        "",
        view["headline"],
        "",
        "## Các lỗi và nội dung cần xác minh",
        "",
        "| Mức | Lỗi/thiếu gì | Lỗi ở đâu | Bằng chứng OCR | Tại sao là lỗi | Cần làm gì | Sau khi sửa | Grounding |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for finding in view["findings"]:
        location = "<br>".join(
            f"{source['source_filename']} — {source['document_title']} — trang {source['page_number']}"
            for source in finding["sources"]
        )
        excerpts = "<br>".join(
            f"[{source['document_id']} trang {source['page_number']}] {source['source_excerpt']}"
            for source in finding["sources"]
        )
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    finding["severity"],
                    finding["what_is_wrong"],
                    location,
                    excerpts,
                    finding["why_it_is_an_issue"],
                    finding["customer_action"] or finding["internal_action"],
                    finding["next_step_after_fix"],
                    finding["grounding_status"],
                )
            )
            + " |"
        )
    lines.extend(["", "## Danh sách yêu cầu khách hàng — gửi một lần", ""])
    if view["one_time_customer_request_list"]:
        lines.extend(f"- {item}" for item in view["one_time_customer_request_list"])
    else:
        lines.append("- Chưa có yêu cầu khách hàng sau khi hợp nhất.")
    lines.extend(["", "## Claim bị bác hoặc mâu thuẫn", ""])
    unsupported = payload["unsupported_or_contradicted_claims"]
    lines.extend(f"- {item}" for item in unsupported)
    if not unsupported:
        lines.append("- Không có claim bị bác trong lượt kiểm chứng.")
    lines.extend(["", "## Fact trọng yếu agent bỏ sót", ""])
    missed = payload["missed_material_facts"]
    if missed:
        for item in missed:
            lines.append(
                f"- **{item['materiality']}** — {item['fact']} — Nguồn: {item['source']} — "
                f"Ảnh hưởng mong đợi: {item['expected_report_effect']}"
            )
    else:
        lines.append("- Không có fact trọng yếu bị bỏ sót trong lượt kiểm chứng.")
    lines.extend(["", "## Sau khi khách hàng sửa/bổ sung", ""])
    lines.extend(f"{index}. {item}" for index, item in enumerate(payload["workflow_after_customer_response"], 1))
    lines.extend(
        [
            "",
            "## Trạng thái checklist tài liệu bắt buộc",
            "",
            f"`{view['required_document_checklist_status']}`",
            "",
            "Nếu checklist bắt buộc chưa được cung cấp từ policy/upstream, hệ thống không được tự kết luận khách hàng thiếu loại giấy tờ nào.",
        ]
    )
    return "\n".join(lines) + "\n"


def _cell(value: object) -> str:
    return str(value).replace("|", "/").replace("\r", " ").replace("\n", " ").strip()


if __name__ == "__main__":
    main()
