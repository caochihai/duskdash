"""Cross-document consistency rules. Conflicts are findings, never corrections."""
from __future__ import annotations

from gateway import db


def cross_validate(case_id: str) -> list[dict]:
    facts = db.list_case_facts(case_id)
    by_key: dict[str, set[str]] = {}
    sources: dict[str, set[str]] = {}
    for fact in facts:
        if fact["key"] == "raw_text_block" or fact["value"] is None:
            continue
        by_key.setdefault(fact["key"], set()).add(fact["normalized_value"])
        sources.setdefault(fact["key"], set()).add(fact["document_type"])

    findings = []
    for key, values in by_key.items():
        if len(values) > 1:
            findings.append({"rule": "cross_document_consistency", "severity": "high",
                             "key": key, "values": sorted(values),
                             "document_types": sorted(sources[key]),
                             "remediation": "Request clarification; do not silently select a value."})
    return findings
