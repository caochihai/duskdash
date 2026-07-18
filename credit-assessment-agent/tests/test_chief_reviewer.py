from app.agents.chief_reviewer import ChiefCreditReviewerAgent, ChiefReviewDraft
from app.agents.document_auditor import DocumentAuditorAgent
from app.engine.policy_engine import evaluate_policy
from app.schemas.common import Decision


class MaliciousReviewerClient:
    def complete_json(self, *, system_prompt, payload, response_model):
        assert response_model is ChiefReviewDraft
        return ChiefReviewDraft(
            decision=Decision.APPROVE,
            decision_summary="LLM attempted to downgrade a hard reject.",
            all_issues=[],
            consolidated_customer_requests=[],
            approval_conditions=[],
            human_review_focus=[],
        )


class FailingReviewerClient:
    def complete_json(self, *, system_prompt, payload, response_model):
        raise ValueError("transient reviewer failure")


def test_chief_cannot_downgrade_hard_reject_or_drop_issues(multi_issue_bundle):
    audit = DocumentAuditorAgent().audit(multi_issue_bundle, run_id="run-test")
    policy = evaluate_policy(audit)
    result = ChiefCreditReviewerAgent(MaliciousReviewerClient()).review(audit, policy)

    assert result.decision == Decision.REJECT
    assert len(result.all_issues) == 5


def test_chief_llm_failure_falls_back_to_deterministic_review(multi_issue_bundle):
    audit = DocumentAuditorAgent().audit(multi_issue_bundle, run_id="run-test")
    policy = evaluate_policy(audit)
    result = ChiefCreditReviewerAgent(FailingReviewerClient(), max_attempts=2).review(audit, policy)

    assert result.decision == policy.decision_candidate
    assert result.all_issues == audit.issues_found
    assert result.decision_summary.startswith("Đề xuất")
    assert result.consolidated_customer_requests
