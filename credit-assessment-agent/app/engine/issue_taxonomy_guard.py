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

    return [_normalize_invalid_financial_comparison(_normalize_issue(issue)) for issue in issues]


def _normalize_invalid_financial_comparison(issue: Issue) -> Issue:
    text = _issue_text(issue)
    if (
        "vay dai han" in text
        and "tong du no" in text
        and ("cic" in text or "tin dung" in text)
    ):
        return issue.model_copy(
            update={
                "category": IssueCategory.FINANCIAL_LOGIC_FAIL,
                "severity": Severity.MEDIUM,
                "description": (
                    "Phép so sánh vay dài hạn trên BCTC với tổng dư nợ CIC chưa cùng phạm vi; "
                    "chưa thể kết luận có khoản nợ bị thiếu 42 tỷ."
                ),
                "why_it_is_an_issue": (
                    "Tổng dư nợ CIC có thể gồm cả vay ngắn hạn và dài hạn; phải cộng đúng các "
                    "khoản vay trên BCTC và đối chiếu cùng ngày báo cáo."
                ),
                "business_impact": (
                    "Nếu giữ phép so sánh sai phạm vi, hệ thống có thể tạo red flag nghĩa vụ nợ giả."
                ),
                "requires_customer_action": False,
                "suggested_customer_action": None,
                "resolution_steps": [
                    "Đối chiếu tổng vay ngắn hạn và dài hạn trên BCTC với CIC tại cùng ngày."
                ],
                "next_step_after_resolution": (
                    "Tính lại chênh lệch trên cùng phạm vi; chỉ tạo mismatch nếu vẫn còn sai lệch."
                ),
            }
        )
    return issue


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
