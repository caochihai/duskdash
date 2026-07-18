from __future__ import annotations

import re
import unicodedata

from app.schemas.common import Issue, IssueCategory, Severity


_TRUE_HARD_STOP_PATTERNS = (
    r"tranh chap",
    r"gia mao",
    r"chu ky (?:bi )?phu nhan",
    r"chu ky khong (?:phai|dung)",
    r"con dau .*khac",
    r"sai chu the",
    r"khong dung chu the",
    r"muc dich (?:su dung )?von .*khong hop le",
    r"bi cam",
    r"khong co nang luc hanh vi",
)

_CAPITAL_PATTERNS = (r"von tu co", r"von doi ung")
_PRE_DISBURSEMENT_PATTERNS = (
    r"truoc khi giai ngan",
    r"truoc giai ngan",
    r"dieu kien giai ngan",
    r"hoan thien .*phap ly",
    r"bo sung ho so hoan cong",
    r"giai chap cua nguoi ban",
)
_MISSING_PATTERNS = (r"thieu tai lieu", r"thieu ho so", r"chua cung cap", r"can bo sung")


def normalize_issue_taxonomy(issues: list[Issue]) -> list[Issue]:
    """Stop free-form LLM labels from turning remediable findings into rejections.

    A HARD_STOP remains one only when its text contains a concrete legal,
    identity, prohibited-purpose, dispute, or forgery signal from the approved
    taxonomy. Everything else is routed to a non-rejecting category for human
    policy classification.
    """

    return [_normalize_issue(issue) for issue in issues]


def is_decision_eligible_hard_stop(issue: Issue) -> bool:
    if issue.category != IssueCategory.HARD_STOP or issue.severity != Severity.CRITICAL:
        return False
    return _matches_any(_issue_text(issue), _TRUE_HARD_STOP_PATTERNS)


def _normalize_issue(issue: Issue) -> Issue:
    if issue.category != IssueCategory.HARD_STOP:
        return issue
    text = _issue_text(issue)
    if _matches_any(text, _TRUE_HARD_STOP_PATTERNS):
        return issue
    if _matches_any(text, _CAPITAL_PATTERNS):
        category = IssueCategory.FINANCIAL_LOGIC_FAIL
    elif _matches_any(text, _PRE_DISBURSEMENT_PATTERNS):
        category = IssueCategory.PRE_DISBURSEMENT_CONDITION
    elif _matches_any(text, _MISSING_PATTERNS):
        category = IssueCategory.MISSING_DOCUMENT
    else:
        category = IssueCategory.POLICY_REVIEW_REQUIRED
    severity = Severity.HIGH if issue.severity == Severity.CRITICAL else issue.severity
    return issue.model_copy(update={"category": category, "severity": severity})


def _issue_text(issue: Issue) -> str:
    material = " ".join(
        filter(
            None,
            [
                issue.description,
                issue.why_it_is_an_issue,
                issue.business_impact,
                issue.suggested_customer_action,
                " ".join(str(item.value) for item in issue.evidence),
            ],
        )
    )
    normalized = unicodedata.normalize("NFKD", material.lower().replace("đ", "d"))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)
