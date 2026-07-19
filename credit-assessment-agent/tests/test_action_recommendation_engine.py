from datetime import date

from app.engine.action_recommendation_engine import build_action_plan, load_action_registry
from app.schemas.policy_action import ActionStatus


def test_same_finding_and_registry_produce_same_actions(multi_issue_bundle):
    from app.orchestration.pipeline import AssessmentPipeline

    view = AssessmentPipeline().assess(multi_issue_bundle).report.banker_view
    assert view is not None
    first = build_action_plan(bundle=multi_issue_bundle, findings=view.findings)
    second = build_action_plan(bundle=multi_issue_bundle, findings=view.findings)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_missing_bank_policy_never_authorizes_customer_request(multi_issue_bundle):
    from app.orchestration.pipeline import AssessmentPipeline

    view = AssessmentPipeline().assess(multi_issue_bundle).report.banker_view
    assert view is not None
    assert view.one_time_customer_request_list == []
    assert view.action_plan.customer_actions == []
    assert any(
        action.action_status == ActionStatus.MANUAL_POLICY_REVIEW_REQUIRED
        for action in view.action_plan.next_actions
    )


def test_expired_rule_is_not_used(multi_issue_bundle):
    from app.orchestration.pipeline import AssessmentPipeline

    view = AssessmentPipeline().assess(multi_issue_bundle).report.banker_view
    assert view is not None
    verified = next(
        finding for finding in view.findings if finding.grounding_status.value == "VERIFIED"
    )
    registry = load_action_registry()
    expired_rules = [
        rule.model_copy(update={"effective_to": date(2025, 12, 31)})
        for rule in registry.rules
    ]
    expired_registry = registry.model_copy(update={"rules": expired_rules})
    plan = build_action_plan(
        bundle=multi_issue_bundle,
        findings=[verified],
        registry=expired_registry,
        as_of=date(2026, 7, 19),
    )
    expired_action = next(
        action
        for action in plan.next_actions
        if action.source_rule_id.endswith("NO-ACTIVE-RULE")
    )
    assert expired_action.action_status == ActionStatus.MANUAL_POLICY_REVIEW_REQUIRED
