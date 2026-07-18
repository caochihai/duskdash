from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one OCR Bundle through the deterministic demo pipeline")
    parser.add_argument("request", type=Path)
    parser.add_argument("response", type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.orchestration.pipeline import AssessmentPipeline
    from app.schemas.input_ocr_bundle import OCRBundle

    bundle = OCRBundle.model_validate_json(args.request.read_text(encoding="utf-8"))
    execution = AssessmentPipeline().assess(bundle)
    args.response.parent.mkdir(parents=True, exist_ok=True)
    args.response.write_text(execution.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "job_id": execution.job_id,
                "processing_status": execution.report.processing_status,
                "decision": execution.report.decision_recommendation,
                "issues": len(execution.report.all_issues),
                "response": str(args.response),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

