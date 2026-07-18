"""Deterministic ownership, citation, calculation, and policy validation."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import AgentOutput


class ValidationOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    validation_status: str
    citation_coverage: Decimal = Field(ge=0, le=1)
    unsupported_claims: tuple[str, ...] = ()
    calculation_errors: tuple[str, ...] = ()
    policy_conflicts: tuple[str, ...] = ()
    agent_contradictions: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    tasks_to_retry: tuple[UUID, ...] = ()
    approved_for_synthesis: bool


class EvidenceValidator:
    """No probabilistic guarantee: validates persisted-reference integrity only."""

    async def validate(
        self,
        outputs: tuple[AgentOutput, ...],
        *,
        authorized_source_ids: frozenset[UUID],
        valid_calculation_ids: frozenset[UUID],
        valid_policy_clause_ids: frozenset[UUID],
    ) -> ValidationOutcome:
        unsupported: list[str] = []
        calculation_errors: list[str] = []
        policy_conflicts: list[str] = []
        contradictions: list[str] = []
        missing_information: list[str] = []
        retry: set[UUID] = set()
        finding_count = 0
        cited_count = 0

        for output in outputs:
            if output.contradictions:
                contradictions.extend(output.contradictions)
                retry.add(output.task_id)
            if output.missing_information:
                missing_information.extend(
                    f"{output.agent_name.value}: {item}" for item in output.missing_information
                )
                retry.add(output.task_id)
            for reference in output.evidence_references:
                if reference.source_id not in authorized_source_ids:
                    unsupported.append(f"unauthorized evidence {reference.source_id}")
                    retry.add(output.task_id)
            for calculation in output.calculations:
                if calculation.calculation_id not in valid_calculation_ids:
                    calculation_errors.append(f"missing calculation {calculation.calculation_id}")
                    retry.add(output.task_id)
            for policy in output.policy_references:
                if policy.clause_id not in valid_policy_clause_ids:
                    policy_conflicts.append(f"missing policy clause {policy.clause_id}")
                    retry.add(output.task_id)
            for finding in output.findings:
                finding_count += 1
                evidence_valid = bool(finding.evidence) and all(
                    reference.source_id in authorized_source_ids for reference in finding.evidence
                )
                calculations_valid = bool(finding.calculation_ids) and all(
                    calculation_id in valid_calculation_ids
                    for calculation_id in finding.calculation_ids
                )
                policies_valid = bool(finding.policy_clause_ids) and all(
                    clause_id in valid_policy_clause_ids for clause_id in finding.policy_clause_ids
                )
                has_invalid_citation = (
                    (finding.evidence and not evidence_valid)
                    or (finding.calculation_ids and not calculations_valid)
                    or (finding.policy_clause_ids and not policies_valid)
                )
                if has_invalid_citation:
                    unsupported.append(f"invalid citation for {finding.title}")
                    retry.add(output.task_id)
                elif evidence_valid or calculations_valid or policies_valid:
                    cited_count += 1
                else:
                    unsupported.append(finding.title)
                    retry.add(output.task_id)

        coverage = Decimal("1") if finding_count == 0 else Decimal(cited_count) / Decimal(finding_count)
        approved = not (
            unsupported
            or calculation_errors
            or policy_conflicts
            or contradictions
            or missing_information
        )
        if approved:
            status = "APPROVED"
        elif unsupported or missing_information:
            status = "INSUFFICIENT_EVIDENCE"
        else:
            status = "REQUIRES_RETRY"
        return ValidationOutcome(
            validation_status=status,
            citation_coverage=coverage.quantize(Decimal("0.00001")),
            unsupported_claims=tuple(unsupported),
            calculation_errors=tuple(calculation_errors),
            policy_conflicts=tuple(policy_conflicts),
            agent_contradictions=tuple(contradictions),
            missing_information=tuple(missing_information),
            tasks_to_retry=tuple(sorted(retry, key=str)),
            approved_for_synthesis=approved,
        )
