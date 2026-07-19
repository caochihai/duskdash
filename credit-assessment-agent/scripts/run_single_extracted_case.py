from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.chief_reviewer import ChiefCreditReviewerAgent
from app.agents.document_auditor import DocumentAuditorAgent
from app.llm_client.glm_client import GLMStructuredClient
from app.orchestration.pipeline import AssessmentPipeline
from app.schemas.input_extracted_bundle import ExtractedCaseBundle


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one upstream-extracted text/data case through the assessment microservice"
    )
    parser.add_argument("input_file", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--mode", choices=("glm", "deterministic"), default="glm")
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--auditor-attempts", type=int, default=1)
    parser.add_argument(
        "--write-normalized-input",
        action="store_true",
        help="Save the canonical v2 text/data-only request next to the report",
    )
    args = parser.parse_args()

    load_dotenv(override=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bundle = ExtractedCaseBundle.model_validate_json(args.input_file.read_text(encoding="utf-8"))
    stem = args.input_file.name.removesuffix(".json")
    if args.write_normalized_input:
        normalized_path = args.output_dir / f"{stem}.extracted-v2.json"
        normalized_path.write_text(
            json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    client: GLMStructuredClient | None = None
    if args.mode == "glm":
        if not os.getenv("GLM_API_KEY"):
            raise SystemExit("GLM_API_KEY is missing from environment/.env")
        client = GLMStructuredClient(timeout_seconds=args.timeout, max_tokens=args.max_tokens)
        pipeline = AssessmentPipeline(
            auditor=DocumentAuditorAgent(client, max_attempts=args.auditor_attempts),
            reviewer=ChiefCreditReviewerAgent(client),
        )
    else:
        pipeline = AssessmentPipeline()

    started = perf_counter()
    try:
        execution = pipeline.assess(bundle)
    finally:
        elapsed_ms = round((perf_counter() - started) * 1000, 3)
    report = execution.report
    llm_calls = [metric.to_dict() for metric in client.call_history] if client else []
    if client:
        client.close()

    payload = {
        "source_input": str(args.input_file),
        "input_contract": "ExtractedCaseBundle/2.0",
        "mode": args.mode,
        "elapsed_ms": elapsed_ms,
        "llm_calls": llm_calls,
        "total_tokens": sum(metric.get("total_tokens") or 0 for metric in llm_calls),
        "execution": execution.model_dump(mode="json"),
    }
    output_json = args.output_dir / f"{stem}.assessment-v2.json"
    output_md = args.output_dir / f"{stem}.assessment-v2.md"
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "case_id": bundle.case_id,
                "success": True,
                "elapsed_ms": elapsed_ms,
                "decision": report.decision_recommendation,
                "findings": report.banker_view.total_findings if report.banker_view else 0,
                "manual_policy_review_required": (
                    report.banker_view.action_plan.manual_policy_review_required
                    if report.banker_view
                    else True
                ),
                "json_report": str(output_json),
                "markdown_report": str(output_md),
            },
            ensure_ascii=False,
        )
    )


def _markdown(payload: dict) -> str:
    report = payload["execution"]["report"]
    view = report.get("banker_view") or {}
    plan = view.get("action_plan") or {}
    lines = [
        f"# Báo cáo xử lý một hồ sơ — {report['customer_id']}",
        "",
        f"- Input: **{payload['input_contract']}** — chỉ text/dữ liệu đã trích xuất",
        f"- Chế độ: **{payload['mode']}**",
        f"- Thời gian: **{payload['elapsed_ms']} ms**",
        f"- Số lượt LLM: **{len(payload['llm_calls'])}**",
        f"- Tổng token: **{payload['total_tokens']}**",
        f"- Trạng thái xử lý: **{report['processing_status']}**",
        f"- Khuyến nghị hiện tại: **{report['decision_recommendation']}**",
        f"- Cần rà soát policy thủ công: **{'Có' if plan.get('manual_policy_review_required') else 'Không'}**",
        "",
        "## Findings có nguồn",
        "",
        "| Mức | Finding | Nguồn chính xác | Grounding | Action ID |",
        "|---|---|---|---|---|",
    ]
    for finding in view.get("findings", []):
        sources = "<br>".join(
            f"{source['source_filename']} — trang {source['page_number']}: {source['source_excerpt']}"
            for source in finding["sources"]
        )
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    finding["severity"],
                    finding["what_is_wrong"],
                    sources,
                    finding["grounding_status"],
                    ", ".join(finding.get("recommended_action_ids", [])),
                )
            )
            + " |"
        )
    lines.extend(["", "## Hành động tiếp theo có căn cứ", ""])
    for action in plan.get("next_actions", []):
        bases = "; ".join(
            f"{basis['document']} — {basis['article']}" for basis in action["legal_basis"]
        ) or "Kiểm soát grounding kỹ thuật"
        bank_basis = "; ".join(
            f"{basis['policy_id']}@{basis['version']} — {basis['section']}"
            for basis in action["bank_policy_basis"]
        ) or "Chưa được cung cấp"
        lines.extend(
            [
                f"### {action['action_id']}",
                "",
                f"- Người xử lý: `{action['owner_role']}`",
                f"- Việc cần làm: `{action['action_type']}`",
                f"- Trạng thái: `{action['action_status']}`",
                f"- Chặn tại bước: `{action['blocking_stage']}`",
                f"- Vì sao: {action['why_required']}",
                f"- Căn cứ pháp lý: {bases}",
                f"- Căn cứ nội bộ: {bank_basis}",
                "- Hoàn thành khi: " + "; ".join(action["completion_criteria"]),
                "",
            ]
        )
    lines.extend(
        [
            "## Giới hạn sử dụng",
            "",
            "Agent không phê duyệt khoản vay. Hành động thiếu căn cứ policy nội bộ được giữ ở "
            "`MANUAL_POLICY_REVIEW_REQUIRED` và không được tự động gửi cho khách hàng.",
        ]
    )
    return "\n".join(lines) + "\n"


def _cell(value: object) -> str:
    return str(value).replace("|", "/").replace("\r", " ").replace("\n", " ").strip()


if __name__ == "__main__":
    main()
