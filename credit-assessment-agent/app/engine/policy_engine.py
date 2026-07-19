from __future__ import annotations

from pydantic import Field

from app.schemas.auditor_report import AuditorReport
from app.schemas.common import CriterionStatus, Decision, IssueCategory, Severity, StrictModel
from app.engine.issue_taxonomy_guard import is_decision_eligible_hard_stop


POLICY_VERSION = "credit-policy-2.0-legal-action-grounded"
DTI_SAFE_MAX = 40.0
DTI_BORDERLINE_MAX = 50.0
DSCR_SAFE_MIN = 1.25
DSCR_BORDERLINE_MIN = 1.0


class PolicyResult(StrictModel):
    decision_candidate: Decision
    reasons: list[str] = Field(min_length=1)
    protected_reject: bool = False
    recalculated_dti_percent: float | None = None
    recalculated_dscr: float | None = None
    dti_decision_eligible: bool = False
    dscr_decision_eligible: bool = False
    decision_input_warnings: list[str] = Field(default_factory=list)


def _recalculate_dti(report: AuditorReport) -> float | None:
    data = report.extracted_data
    if data.recognized_monthly_income is None or data.recognized_monthly_income <= 0:
        return None
    if data.existing_monthly_debt_service is None or data.proposed_monthly_debt_service is None:
        return None
    return round(
        (data.existing_monthly_debt_service + data.proposed_monthly_debt_service)
        / data.recognized_monthly_income
        * 100,
        4,
    )


def _recalculate_dscr(report: AuditorReport) -> float | None:
    data = report.extracted_data
    if data.cfads is None or data.total_debt_service is None or data.total_debt_service <= 0:
        return None
    return round(data.cfads / data.total_debt_service, 4)


def _all_required_criteria_pass(report: AuditorReport) -> bool:
    groups = report.criterion_results
    criteria = groups.hard_stop + groups.cic + groups.financial_logic + groups.cross_check
    return all(item.status in {CriterionStatus.PASS, CriterionStatus.NOT_APPLICABLE} for item in criteria)


def evaluate_policy(
    report: AuditorReport,
    *,
    verified_issue_ids: set[str] | None = None,
    verified_metric_names: set[str] | None = None,
    required_checklist_verified: bool = True,
) -> PolicyResult:
    """Apply the hard decision matrix from sections 11 and 13."""

    issues = report.issues_found
    dti = _recalculate_dti(report)
    dscr = _recalculate_dscr(report)
    issue_is_verified = (
        (lambda issue_id: True)
        if verified_issue_ids is None
        else (lambda issue_id: issue_id in verified_issue_ids)
    )
    metric_is_verified = (
        (lambda metric: True)
        if verified_metric_names is None
        else (lambda metric: metric in verified_metric_names)
    )
    dti_eligible = dti is not None and metric_is_verified("dti")
    dscr_eligible = dscr is not None and metric_is_verified("dscr")
    warnings: list[str] = []
    if dti is not None and not dti_eligible:
        warnings.append("DTI_OPERANDS_NOT_VERIFIED")
    if dscr is not None and not dscr_eligible:
        warnings.append("DSCR_OPERANDS_NOT_VERIFIED")
    if not required_checklist_verified:
        warnings.extend(
            [
                "REQUIRED_DOCUMENT_CHECKLIST_NOT_PROVIDED",
                "BANK_DECISION_POLICY_NOT_CONFIGURED",
            ]
        )

    # Public law defines mandatory conditions and governance duties, but bank-specific
    # thresholds/exception paths must come from an approved internal policy. Without
    # that input, no hard-coded DTI/DSCR/CIC value may automatically approve or reject.
    if not required_checklist_verified:
        return PolicyResult(
            decision_candidate=Decision.PENDING,
            reasons=["MANUAL_POLICY_REVIEW_REQUIRED"],
            recalculated_dti_percent=dti,
            recalculated_dscr=dscr,
            dti_decision_eligible=False,
            dscr_decision_eligible=False,
            decision_input_warnings=warnings,
        )

    critical_hard_stop = any(
        is_decision_eligible_hard_stop(issue) and issue_is_verified(issue.issue_id)
        for issue in issues
    )
    if critical_hard_stop:
        return PolicyResult(
            decision_candidate=Decision.REJECT,
            reasons=["CRITICAL_HARD_STOP"],
            protected_reject=True,
            recalculated_dti_percent=dti,
            recalculated_dscr=dscr,
            dti_decision_eligible=dti_eligible,
            dscr_decision_eligible=dscr_eligible,
            decision_input_warnings=warnings,
        )

    unverified_critical_hard_stop = any(
        is_decision_eligible_hard_stop(issue) and not issue_is_verified(issue.issue_id)
        for issue in issues
    )

    cic_unacceptable = (
        metric_is_verified("highest_cic_group")
        and (report.extracted_data.highest_cic_group or 0) >= 3
    ) or any(
        issue.category == IssueCategory.CIC_RED_FLAG
        and issue.severity == Severity.CRITICAL
        and issue_is_verified(issue.issue_id)
        for issue in issues
    )
    if cic_unacceptable:
        return PolicyResult(
            decision_candidate=Decision.REJECT,
            reasons=["UNACCEPTABLE_CIC"],
            protected_reject=True,
            recalculated_dti_percent=dti,
            recalculated_dscr=dscr,
            dti_decision_eligible=dti_eligible,
            dscr_decision_eligible=dscr_eligible,
            decision_input_warnings=warnings,
        )

    financial_critical = any(
        issue.category == IssueCategory.FINANCIAL_LOGIC_FAIL and issue.severity == Severity.CRITICAL
        and issue_is_verified(issue.issue_id)
        for issue in issues
    )
    cannot_repay = financial_critical or (dti_eligible and dti > DTI_BORDERLINE_MAX) or (
        dscr_eligible and dscr < DSCR_BORDERLINE_MIN
    )
    if cannot_repay:
        return PolicyResult(
            decision_candidate=Decision.REJECT,
            reasons=["INSUFFICIENT_REPAYMENT_CAPACITY"],
            protected_reject=True,
            recalculated_dti_percent=dti,
            recalculated_dscr=dscr,
            dti_decision_eligible=dti_eligible,
            dscr_decision_eligible=dscr_eligible,
            decision_input_warnings=warnings,
        )

    unverified_blocking_issue = unverified_critical_hard_stop or any(
        issue.severity in {Severity.CRITICAL, Severity.HIGH}
        and not issue_is_verified(issue.issue_id)
        for issue in issues
    )
    if unverified_blocking_issue or warnings:
        return PolicyResult(
            decision_candidate=Decision.PENDING,
            reasons=["UNVERIFIED_DECISION_INPUT"],
            recalculated_dti_percent=dti,
            recalculated_dscr=dscr,
            dti_decision_eligible=dti_eligible,
            dscr_decision_eligible=dscr_eligible,
            decision_input_warnings=warnings,
        )

    high_mismatch = any(
        issue.category == IssueCategory.CROSS_CHECK_MISMATCH
        and issue.severity in {Severity.HIGH, Severity.CRITICAL}
        for issue in issues
    )
    unknown_criteria = any(
        item.status == CriterionStatus.UNKNOWN
        for group in (
            report.criterion_results.hard_stop,
            report.criterion_results.cic,
            report.criterion_results.financial_logic,
            report.criterion_results.cross_check,
        )
        for item in group
    )
    if high_mismatch or unknown_criteria:
        reason = "UNRESOLVED_HIGH_SEVERITY_MISMATCH" if high_mismatch else "INSUFFICIENT_EVIDENCE"
        return PolicyResult(
            decision_candidate=Decision.PENDING,
            reasons=[reason],
            recalculated_dti_percent=dti,
            recalculated_dscr=dscr,
        )

    borderline = (dti_eligible and DTI_SAFE_MAX < dti <= DTI_BORDERLINE_MAX) or (
        dscr_eligible and DSCR_BORDERLINE_MIN <= dscr < DSCR_SAFE_MIN
    )
    if borderline:
        return PolicyResult(
            decision_candidate=Decision.APPROVE_WITH_CONDITIONS,
            reasons=["BORDERLINE_FINANCIAL_METRICS"],
            recalculated_dti_percent=dti,
            recalculated_dscr=dscr,
            dti_decision_eligible=dti_eligible,
            dscr_decision_eligible=dscr_eligible,
            decision_input_warnings=warnings,
        )

    if _all_required_criteria_pass(report):
        return PolicyResult(
            decision_candidate=Decision.APPROVE,
            reasons=["ALL_REQUIRED_CRITERIA_PASS"],
            recalculated_dti_percent=dti,
            recalculated_dscr=dscr,
            dti_decision_eligible=dti_eligible,
            dscr_decision_eligible=dscr_eligible,
            decision_input_warnings=warnings,
        )

    return PolicyResult(
        decision_candidate=Decision.PENDING,
        reasons=["POLICY_REVIEW_REQUIRED"],
        recalculated_dti_percent=dti,
        recalculated_dscr=dscr,
        dti_decision_eligible=dti_eligible,
        dscr_decision_eligible=dscr_eligible,
        decision_input_warnings=warnings,
    )
