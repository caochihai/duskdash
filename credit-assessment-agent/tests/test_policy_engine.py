from app.agents.document_auditor import DocumentAuditorAgent
from app.engine.policy_engine import evaluate_policy
from app.schemas.common import Decision


def test_clean_case_approves(clean_bundle):
    audit = DocumentAuditorAgent().audit(clean_bundle, run_id="run-test")
    assert evaluate_policy(audit).decision_candidate == Decision.APPROVE


def test_borderline_case_has_conditions(borderline_bundle):
    audit = DocumentAuditorAgent().audit(borderline_bundle, run_id="run-test")
    result = evaluate_policy(audit)
    assert result.decision_candidate == Decision.APPROVE_WITH_CONDITIONS
    assert result.recalculated_dti_percent == 45.0


def test_critical_hard_stop_is_protected_reject(multi_issue_bundle):
    audit = DocumentAuditorAgent().audit(multi_issue_bundle, run_id="run-test")
    result = evaluate_policy(audit)
    assert result.decision_candidate == Decision.REJECT
    assert result.protected_reject is True


def test_policy_is_deterministic_across_ten_runs(multi_issue_bundle):
    audit = DocumentAuditorAgent().audit(multi_issue_bundle, run_id="run-test")
    outputs = [evaluate_policy(audit).model_dump(mode="json") for _ in range(10)]
    assert outputs == [outputs[0]] * 10

