"""Compliance expert limited to approved policy references."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.agents.base import AgentInput, AgentName, AgentOutput, FindingDraft, PolicyReference


class ComplianceAgent:
    name = AgentName.LEGAL_COMPLIANCE

    async def run(self, request: AgentInput) -> AgentOutput:
        raw = request.context.get("policy_references", ())
        policies = tuple(PolicyReference.model_validate(item) for item in raw) if isinstance(raw, (list, tuple)) else ()
        checks = request.context.get("policy_checks", ())
        findings: list[FindingDraft] = []
        if isinstance(checks, (list, tuple)):
            for check in checks:
                if not isinstance(check, dict) or check.get("status") not in {"FAIL", "CONDITIONAL"}:
                    continue
                findings.append(
                    FindingDraft(
                        finding_type="POLICY_CHECK",
                        title=str(check.get("rule_code", "Policy condition")),
                        description=str(check.get("explanation", "Policy condition requires review.")),
                        severity="HIGH" if check.get("status") == "FAIL" else "MEDIUM",
                        confidence=Decimal("1"),
                        recommended_action="Review the cited effective policy clause.",
                        policy_clause_ids=_policy_clause_ids(check, policies),
                    )
                )
        missing = () if policies else ("approved effective policy reference",)
        return AgentOutput(
            agent_name=self.name,
            task_id=request.task_id,
            conclusion="Policy checks use only supplied approved policy versions.",
            findings=tuple(findings),
            policy_references=policies,
            missing_information=missing,
            limitations=("No uncited model legal knowledge was used.",),
            recommended_action="Resolve failed or conditional checks with an authorized reviewer.",
            confidence=Decimal("0.95") if policies else Decimal("0.20"),
        )


def _policy_clause_ids(
    check: dict[object, object], policies: tuple[PolicyReference, ...]
) -> tuple[UUID, ...]:
    raw_clause_id = check.get("clause_id")
    if raw_clause_id is not None:
        try:
            clause_id = UUID(str(raw_clause_id))
        except ValueError:
            return ()
        if any(policy.clause_id == clause_id for policy in policies):
            return (clause_id,)
        return ()
    return tuple(policy.clause_id for policy in policies)
