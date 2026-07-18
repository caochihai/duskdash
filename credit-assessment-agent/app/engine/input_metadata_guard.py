from __future__ import annotations

import re
import unicodedata

from app.schemas.common import Issue, IssueCategory
from app.schemas.input_ocr_bundle import OCRBundle


DATASET_MARKER_TERMS = ("ma so giay to", "qr", "ma tra cuu", "con dau", "gia lap")


def remove_dataset_marker_false_positives(bundle: OCRBundle, issues: list[Issue]) -> list[Issue]:
    """Remove a synthetic-dataset footer when it was misclassified as customer fraud.

    The guard is deliberately narrow: the same marker must occur on at least half
    of readable pages, the issue must be a HARD_STOP, and its description must
    explicitly rely on the word "giả lập". Specific forgery evidence such as
    signature, seal, identity or date mismatches remains untouched.
    """

    readable = [page for page in bundle.ocr_pages if page.ocr_text.strip()]
    if not readable:
        return issues
    marker_pages = sum(_is_dataset_marker_page(page.ocr_text) for page in readable)
    if marker_pages / len(readable) < 0.5:
        return issues
    return [issue for issue in issues if not _is_marker_only_hard_stop(issue)]


def _is_dataset_marker_page(text: str) -> bool:
    normalized = _normalize(text)
    return all(term in normalized for term in DATASET_MARKER_TERMS)


def _is_marker_only_hard_stop(issue: Issue) -> bool:
    if issue.category != IssueCategory.HARD_STOP:
        return False
    description = _normalize(issue.description)
    if "gia lap" not in description:
        return False
    specific_forgery_terms = (
        "chu ky",
        "hai mau dau",
        "metadata chinh sua",
        "ngay ky truoc",
        "cccd trung",
        "chu the khong khop",
    )
    return not any(term in description for term in specific_forgery_terms)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()
