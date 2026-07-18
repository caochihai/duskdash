from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.input_ocr_bundle import OCRBundle
from scripts.build_ocr_bundle import EasyOCREngine, build_bundle, slugify


def main() -> None:
    parser = argparse.ArgumentParser(description="Build OCR bundles for every case directory")
    parser.add_argument("input_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    case_dirs = sorted(
        (path for path in args.input_root.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    )
    if not case_dirs:
        raise SystemExit(f"No case directories found in {args.input_root}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    engine = EasyOCREngine(args.output_dir / ".ocr-cache")
    results: list[dict[str, object]] = []
    for case_dir in case_dirs:
        output = args.output_dir / f"{slugify(case_dir.name).lower()}.ocr-bundle.json"
        bundle = OCRBundle.model_validate(build_bundle(case_dir, engine))
        output.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        result = {
            "case": case_dir.name,
            "output": str(output),
            "documents": bundle.document_manifest.total_documents,
            "pages": bundle.document_manifest.total_pages,
            "unreadable": sum(page.page_quality_flag == "UNREADABLE" for page in bundle.ocr_pages),
        }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    print(json.dumps({"completed": len(results), "results": results}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
