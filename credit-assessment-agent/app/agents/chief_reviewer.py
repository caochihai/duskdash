from __future__ import annotations

from collections import defaultdict

import httpx
from pydantic import Field
from pydantic import ValidationError

from app.agents.prompts import CHIEF_REVIEWER_SYSTEM_PROMPT
from app.engine.policy_engine import PolicyResult
from app.llm_client.anthropic_client import StructuredLLMClient
from app.schemas.auditor_report import AuditorReport
from app.schemas.common import Decision, Issue, Severity, StrictModel
from app.schemas.output_report import ApprovalCondition, CustomerRequest


class ChiefReviewDraft(StrictModel):
    decision: Decision
    decision_summary: str = Field(min_length=1)
    all_issues: list[Issue]
    consolidated_customer_requests: list[CustomerRequest]
    approval_conditions: list[ApprovalCondition]
    human_review_focus: list[str]


class ChiefCreditReviewerAgent:
    def __init__(self, client: StructuredLLMClient | None = None, *, max_attempts: int = 2) -> None:
        self._client = client
        self._max_attempts = max_attempts

    def review(self, audit: AuditorReport, policy: PolicyResult) -> ChiefReviewDraft:
        if self._client is None:
            draft = _deterministic_review(audit, policy)
        else:
            errors: list[str] = []
            for attempt in range(1, self._max_attempts + 1):
                try:
                    draft = self._client.complete_json(
                        system_prompt=CHIEF_REVIEWER_SYSTEM_PROMPT,
                        payload={
                            "validated_auditor_report": audit.model_dump(mode="json"),
                            "deterministic_policy_result": policy.model_dump(mode="json"),
                            "attempt": attempt,
                            "validation_feedback": errors[-1] if errors else None,
                        },
                        response_model=ChiefReviewDraft,
                    )
                    break
                except (ValidationError, ValueError, httpx.HTTPError) as exc:
                    errors.append(str(exc))
            else:
                # The reviewer is a presentation layer. A transient LLM/API
                # failure must not discard the already validated audit and
                # deterministic policy result.
                draft = _deterministic_review(audit, policy)

        safe_draft = _deterministic_review(audit, policy)
        # Code owns every decision-affecting field. The LLM draft is advisory only;
        # it cannot re-label issues, invent requests, or restate an unsafe decision.
        return draft.model_copy(
            update={
                "decision": policy.decision_candidate,
                "all_issues": audit.issues_found,
                "decision_summary": safe_draft.decision_summary,
                "consolidated_customer_requests": safe_draft.consolidated_customer_requests,
                "approval_conditions": safe_draft.approval_conditions,
                "human_review_focus": safe_draft.human_review_focus,
            }
        )


def _deterministic_review(audit: AuditorReport, policy: PolicyResult) -> ChiefReviewDraft:
    grouped: dict[str, list[Issue]] = defaultdict(list)
    for issue in audit.issues_found:
        key = issue.suggested_customer_action or f"{issue.category}:{issue.location.field_name or ''}"
        grouped[key].append(issue)

    requests: list[CustomerRequest] = []
    for index, (key, grouped_issues) in enumerate(grouped.items(), start=1):
        actionable = [issue for issue in grouped_issues if issue.requires_customer_action]
        if not actionable:
            continue
        priority = min((issue.severity for issue in actionable), key=_severity_rank)
        action = actionable[0].suggested_customer_action
        if not action:
            action = "Bổ sung hoặc giải trình: " + "; ".join(issue.description for issue in actionable)
        requests.append(
            CustomerRequest(
                request_id=f"REQ-{index:03d}",
                request=action,
                related_issue_ids=[issue.issue_id for issue in actionable],
                priority=priority,
            )
        )

    metrics = audit.extracted_data
    metric_parts: list[str] = []
    if policy.recalculated_dti_percent is not None:
        metric_parts.append(f"DTI={policy.recalculated_dti_percent:.1f}%")
    if policy.recalculated_dscr is not None:
        metric_parts.append(f"DSCR={policy.recalculated_dscr:.2f}")
    if metrics.highest_cic_group is not None:
        metric_parts.append(f"nhóm CIC cao nhất={metrics.highest_cic_group}")
    issue_summary = f"Phát hiện {len(audit.issues_found)} vấn đề trên toàn bộ hồ sơ."
    summary = (
        f"Đề xuất {policy.decision_candidate.value} theo policy xác định: "
        f"{', '.join(policy.reasons)}. {issue_summary}"
    )
    if metric_parts:
        summary += " Chỉ số chính: " + ", ".join(metric_parts) + "."
    if policy.decision_input_warnings:
        summary += " Cảnh báo dữ liệu quyết định: " + ", ".join(policy.decision_input_warnings) + "."
    if policy.recalculated_dti_percent is not None and not policy.dti_decision_eligible:
        summary += " DTI chỉ là số tham khảo vì các toán hạng chưa được xác minh nguồn."
    if policy.recalculated_dscr is not None and not policy.dscr_decision_eligible:
        summary += " DSCR chỉ là số tham khảo vì các toán hạng chưa được xác minh nguồn."

    conditions: list[ApprovalCondition] = []
    if policy.decision_candidate == Decision.APPROVE_WITH_CONDITIONS:
        conditions.append(
            ApprovalCondition(
                condition="Điều chỉnh cấu trúc khoản vay để đưa DTI/DSCR về vùng an toàn.",
                purpose="Giảm rủi ro trả nợ tại vùng biên.",
            )
        )

    focus = [issue.description for issue in sorted(audit.issues_found, key=lambda i: _severity_rank(i.severity))[:5]]
    if policy.decision_input_warnings:
        focus.insert(0, "Xử lý cảnh báo đầu vào: " + ", ".join(policy.decision_input_warnings))
    if not focus:
        focus = ["Xác nhận lần cuối tính đầy đủ và nguồn trả nợ trước quyết định của con người."]

    return ChiefReviewDraft(
        decision=policy.decision_candidate,
        decision_summary=summary,
        all_issues=audit.issues_found,
        consolidated_customer_requests=requests,
        approval_conditions=conditions,
        human_review_focus=focus,
    )


def _severity_rank(severity: Severity) -> int:
    return {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }[severity]
