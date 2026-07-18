from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from pydantic import Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm_client.glm_client import GLMStructuredClient
from app.schemas.common import StrictModel


JUDGE_PROMPT = """Bạn là kiểm định viên độc lập về chất lượng báo cáo thẩm định tín dụng.
Bạn KHÔNG chấm code, kiến trúc, test hay mức độ production-ready. Bạn chỉ so sánh REPORT của
microservice với SOURCE OCR đã cung cấp. OCR có thể nhiễu; không coi ký tự OCR mơ hồ là bằng chứng chắc chắn.

Yêu cầu:
1. Kiểm tra từng kết luận, số liệu, issue và quyết định trong REPORT có bằng chứng trong SOURCE hay không.
2. Chỉ ra claim không được hỗ trợ, số liệu sai, nguồn dẫn sai và fact trọng yếu bị bỏ sót.
3. Kiểm tra report có đọc đủ mọi trang và có phân biệt UNKNOWN với PASS hay không.
4. Đánh giá quyết định theo chính các fact có trong SOURCE; không tự bổ sung chính sách bên ngoài.
5. Với mỗi nhận định quan trọng, dẫn document_id/source_filename và trích đoạn ngắn từ OCR.
6. Điểm overall là trung bình có cân nhắc 5 tiêu chí; hallucination nghiêm trọng hoặc quyết định không có
   căn cứ phải khiến verdict=FAIL. PASS >=8, CONDITIONAL_PASS từ 6 đến dưới 8, FAIL <6.
Chỉ trả JSON theo schema."""


class EvidenceCheck(StrictModel):
    report_claim: str
    status: str = Field(pattern="^(SUPPORTED|PARTIALLY_SUPPORTED|UNSUPPORTED|CONTRADICTED)$")
    source: str
    source_excerpt: str
    explanation: str


class MissedFact(StrictModel):
    fact: str
    materiality: str = Field(pattern="^(HIGH|MEDIUM|LOW)$")
    source: str
    source_excerpt: str
    expected_report_effect: str


class ContentEvaluation(StrictModel):
    case_id: str
    verdict: str = Field(pattern="^(PASS|CONDITIONAL_PASS|FAIL)$")
    overall_score: float = Field(ge=0, le=10)
    evidence_grounding_score: float = Field(ge=0, le=10)
    completeness_score: float = Field(ge=0, le=10)
    numerical_consistency_score: float = Field(ge=0, le=10)
    decision_logic_score: float = Field(ge=0, le=10)
    actionability_score: float = Field(ge=0, le=10)
    decision_supported: bool
    report_decision: str | None
    independently_supported_decision: str
    executive_assessment: str
    evidence_checks: list[EvidenceCheck]
    unsupported_or_contradicted_claims: list[str]
    missed_material_facts: list[MissedFact]
    ocr_quality_caveats: list[str]
    recommended_corrections: list[str]
    confidence: float = Field(ge=0, le=1)


def compact_source(bundle: dict) -> dict:
    return {
        "case_id": bundle["case_id"],
        "customer_id": bundle["customer_id"],
        "manifest": bundle["document_manifest"],
        "pages": [
            {
                "document_id": page["document_id"],
                "page_number": page["page_number"],
                "source_filename": page.get("ocr_fields", {}).get("source_filename"),
                "ocr_confidence": page["ocr_confidence"],
                "page_quality_flag": page["page_quality_flag"],
                "ocr_text": page["ocr_text"],
            }
            for page in bundle["ocr_pages"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge assessment content against source OCR with GLM")
    parser.add_argument("assessment_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()

    load_dotenv(override=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(args.assessment_dir.glob("*.assessment.json"))
    if not files:
        raise SystemExit(f"No assessment artifacts found in {args.assessment_dir}")

    client = GLMStructuredClient(timeout_seconds=args.timeout, max_tokens=args.max_tokens)
    summaries: list[dict[str, object]] = []
    try:
        for path in files:
            artifact = json.loads(path.read_text(encoding="utf-8"))
            if not artifact.get("success"):
                summaries.append({"artifact": path.name, "evaluated": False, "reason": "assessment_failed"})
                continue
            bundle_path = Path(artifact["source_bundle"])
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            report = artifact["execution"]["report"]
            client.reset_metrics()
            started = perf_counter()
            try:
                evaluation = client.complete_json(
                    system_prompt=JUDGE_PROMPT,
                    payload={"source": compact_source(bundle), "report": report},
                    response_model=ContentEvaluation,
                )
                elapsed_ms = round((perf_counter() - started) * 1000, 3)
                result = {
                    "assessment_artifact": str(path),
                    "success": True,
                    "elapsed_ms": elapsed_ms,
                    "llm_calls": [metric.to_dict() for metric in client.call_history],
                    "evaluation": evaluation.model_dump(mode="json"),
                }
                summary = {
                    "case_id": evaluation.case_id,
                    "evaluated": True,
                    "verdict": evaluation.verdict,
                    "overall_score": evaluation.overall_score,
                    "decision_supported": evaluation.decision_supported,
                    "elapsed_ms": elapsed_ms,
                    "total_tokens": sum(metric.total_tokens or 0 for metric in client.call_history),
                }
            except Exception as exc:
                elapsed_ms = round((perf_counter() - started) * 1000, 3)
                result = {
                    "assessment_artifact": str(path),
                    "success": False,
                    "elapsed_ms": elapsed_ms,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "llm_calls": [metric.to_dict() for metric in client.call_history],
                }
                summary = {
                    "artifact": path.name,
                    "evaluated": False,
                    "reason": type(exc).__name__,
                    "elapsed_ms": elapsed_ms,
                }

            output = args.output_dir / f"{path.stem}.content-evaluation.json"
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            summaries.append(summary)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        client.close()

    summary_path = args.output_dir / "content-evaluation-summary.json"
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "cases": len(summaries)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
