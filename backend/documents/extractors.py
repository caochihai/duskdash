"""Deterministic first-pass extractors for common SME-loan documents."""
from __future__ import annotations

import re

from common.schemas import new_id


def _fact(key: str, value: str, evidence: dict, confidence: float = 0.8) -> dict:
    return {"fact_id": new_id("fact"), "key": key, "value": value,
            "normalized_value": re.sub(r"\s+", " ", value).strip().lower(),
            "confidence": confidence, "evidence": evidence,
            "extractor_version": "regex-document-v1"}


def extract(document_type: str, blocks: list[dict]) -> list[dict]:
    """Extract conservative facts; each result retains source-page evidence."""
    patterns: dict[str, list[tuple[str, str]]] = {
        "dkkd": [("enterprise_id", r"(?:mã số doanh nghiệp|mã số thuế|mst)\s*[:：]?\s*([0-9-]{10,14})")],
        "bctc": [("revenue", r"(?:doanh thu|revenue)\s*[:：]?\s*([\d., ]+)")],
        "sao_ke": [("account_number", r"(?:số tài khoản|account(?: number)?)\s*[:：]?\s*([0-9]{6,20})")],
        "cccd": [("id_number", r"(?:số|no\.?|number)\s*(?:cccd|cmnd|id)\s*[:：]?\s*([0-9]{9,12})")],
        "so_do": [("certificate_id", r"(?:số (?:giấy chứng nhận|sổ)|certificate(?: no\.?)?)\s*[:：]?\s*([A-Z0-9-]{5,})")],
    }
    results: list[dict] = []
    for block in blocks:
        text = block["text"]
        for key, pattern in patterns.get(document_type, []):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                results.append(_fact(key, match.group(1), {
                    "page": block["page"], "bbox": block.get("bbox"), "text": text[:500],
                }))
    return results
