from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class RiskFinding(BaseModel):
    severity: Literal["critical", "high", "medium", "low"]
    finding: str
    evidence: str
    impact: str


class GLMTestEvaluation(BaseModel):
    verdict: Literal["PASS_FOR_DEMO", "CONDITIONAL_PASS", "NOT_READY"]
    overall_score: float = Field(ge=0, le=10)
    demo_readiness_score: float = Field(ge=0, le=10)
    production_readiness_score: float = Field(ge=0, le=10)
    executive_summary: str
    strengths: list[str]
    risks: list[RiskFinding]
    missing_tests: list[str]
    prioritized_actions: list[str]
    confidence: float = Field(ge=0, le=1)


def _test_report(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    cases: list[dict[str, str]] = []
    for suite in suites:
        for case in suite.findall("testcase"):
            status = "passed"
            if case.find("failure") is not None:
                status = "failed"
            elif case.find("error") is not None:
                status = "error"
            elif case.find("skipped") is not None:
                status = "skipped"
            cases.append(
                {
                    "classname": case.attrib.get("classname", ""),
                    "name": case.attrib.get("name", ""),
                    "status": status,
                }
            )
    return {
        "tests": sum(int(suite.attrib.get("tests", 0)) for suite in suites),
        "failures": sum(int(suite.attrib.get("failures", 0)) for suite in suites),
        "errors": sum(int(suite.attrib.get("errors", 0)) for suite in suites),
        "skipped": sum(int(suite.attrib.get("skipped", 0)) for suite in suites),
        "time_seconds": sum(float(suite.attrib.get("time", 0)) for suite in suites),
        "cases": cases,
    }


def _coverage_report(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    files = report.get("files", {})
    selected = {
        name: details.get("summary", {}).get("percent_covered")
        for name, details in files.items()
        if any(
            marker in name.replace("\\", "/")
            for marker in (
                "agents/document_auditor.py",
                "agents/chief_reviewer.py",
                "engine/completeness_gate.py",
                "engine/policy_engine.py",
                "llm_client/glm_client.py",
                "orchestration/pipeline.py",
                "schemas/input_ocr_bundle.py",
                "schemas/output_report.py",
            )
        )
    }
    return {
        "total_percent_covered": report["totals"]["percent_covered"],
        "covered_lines": report["totals"]["covered_lines"],
        "missing_lines": report["totals"]["missing_lines"],
        "selected_modules": selected,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Ask GLM-5.2 to independently evaluate test evidence")
    parser.add_argument("junit_xml", type=Path)
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    load_dotenv(project_root / ".env", override=True)
    from app.llm_client.glm_client import GLMStructuredClient

    evidence = {
        "test_report": _test_report(args.junit_xml),
        "coverage_report": _coverage_report(args.coverage_json),
        "system_invariants": [
            "No early termination: all manifest pages must be audited.",
            "UNKNOWN must never become PASS.",
            "Completeness Gate runs outside the LLM.",
            "Policy Engine owns the decision candidate.",
            "Chief Reviewer cannot downgrade protected REJECT or drop validated issues.",
            "Unverified external OCR cannot be approved by deterministic demo mode.",
        ],
        "known_scope": {
            "service": "FastAPI credit-document assessment microservice",
            "llm_adapter": "GLM-5.2 via FPT AI Marketplace OpenAI-compatible endpoint",
            "human_final_decision": True,
            "cache": "in-memory demo cache",
        },
        "review_instruction": (
            "Đánh giá độc lập mức sẵn sàng demo và production. Chỉ dùng bằng chứng được cung cấp; "
            "không coi coverage cao là bằng chứng đủ cho nghiệp vụ ngân hàng. Nêu rõ test còn thiếu."
        ),
    }
    client = GLMStructuredClient(timeout_seconds=180)
    try:
        evaluation = client.complete_json(
            system_prompt=(
                "Bạn là Principal QA Architect và AI Risk Reviewer độc lập cho hệ thống thẩm định tín dụng. "
                "Phải phân biệt test pass với production readiness, ưu tiên an toàn và khả năng truy vết."
            ),
            payload=evidence,
            response_model=GLMTestEvaluation,
        )
    finally:
        client.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(evaluation.model_dump_json(indent=2), encoding="utf-8")
    print(evaluation.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
