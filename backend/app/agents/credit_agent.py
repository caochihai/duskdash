"""Credit expert that interprets persisted deterministic calculation results."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.agents.base import AgentInput, AgentName, AgentOutput, CalculationReference, FindingDraft

_REQUIRED_REPAYMENT_METRICS = (
    "DTI",
    "DSCR",
    "NET_DISPOSABLE_INCOME",
    "EXISTING_MONTHLY_OBLIGATIONS",
)


class CreditCalculationTool(Protocol):
    async def calculate_for_analysis(self, request: AgentInput) -> tuple[CalculationReference, ...]: ...


class CreditAgent:
    """Interpret calculations without applying policy thresholds or creating a decision."""

    name = AgentName.CREDIT

    def __init__(self, calculator: CreditCalculationTool) -> None:
        self._calculator = calculator

    async def run(self, request: AgentInput) -> AgentOutput:
        calculations = await self._calculator.calculate_for_analysis(request)
        metrics = _repayment_metrics(calculations)
        missing = tuple(
            f"persisted {metric} calculation"
            for metric in _REQUIRED_REPAYMENT_METRICS
            if metric not in metrics
        )
        risk_flags: set[str] = set()
        findings: list[FindingDraft] = []
        calculation_ids = tuple(dict.fromkeys(item.calculation_id for item in calculations))

        invalid = [name for name, value in metrics.items() if value < 0 and name != "NET_DISPOSABLE_INCOME"]
        if invalid:
            risk_flags.update(f"INVALID_{name}" for name in invalid)
            findings.append(
                FindingDraft(
                    finding_type="CALCULATION_ANOMALY",
                    title="Repayment calculation contains invalid negative values",
                    description=(
                        "Persisted deterministic calculations contain invalid negative values for: "
                        f"{', '.join(sorted(invalid))}."
                    ),
                    severity="HIGH",
                    confidence=Decimal("1"),
                    recommended_action="Review persisted calculation inputs and source references.",
                    calculation_ids=calculation_ids,
                )
            )

        net_disposable_income = metrics.get("NET_DISPOSABLE_INCOME")
        if net_disposable_income is not None and net_disposable_income < 0:
            risk_flags.add("NEGATIVE_NET_DISPOSABLE_INCOME")
            findings.append(
                _calculation_finding(
                    calculations,
                    metric="NET_DISPOSABLE_INCOME",
                    finding_type="REPAYMENT_CAPACITY_RISK",
                    title="Negative net disposable income",
                    description=(
                        "The persisted deterministic net disposable income is negative after existing "
                        "obligations and the projected payment."
                    ),
                    severity="HIGH",
                    action="Review verified income, debt obligations, and proposed loan terms.",
                )
            )
        elif net_disposable_income == 0:
            risk_flags.add("NO_DISPOSABLE_INCOME_BUFFER")

        dti = metrics.get("DTI")
        dscr = metrics.get("DSCR")
        if (dti is not None and dti > 1) or (dscr is not None and 0 <= dscr < 1):
            risk_flags.add("DEBT_SERVICE_EXCEEDS_ACCEPTED_INCOME")
        if dti == 1 or dscr == 1:
            risk_flags.add("NO_INCOME_BUFFER_AFTER_DEBT_SERVICE")

        obligations = metrics.get("EXISTING_MONTHLY_OBLIGATIONS")
        if obligations is not None and obligations > 0:
            risk_flags.add("EXISTING_DEBT_OBLIGATIONS_PRESENT")

        if missing:
            risk_flags.add("INCOMPLETE_REPAYMENT_CALCULATIONS")

        for metric in _REQUIRED_REPAYMENT_METRICS:
            value = metrics.get(metric)
            if value is None:
                continue
            cited_calculations = tuple(
                calculation.calculation_id
                for calculation in calculations
                if _calculation_contains_metric(calculation, metric)
            )
            findings.append(
                FindingDraft(
                    finding_type="REPAYMENT_INDICATOR",
                    title=f"Persisted {metric} indicator",
                    description=(
                        f"The persisted deterministic {metric} result is {value}; "
                        "no policy threshold or loan decision was applied."
                    ),
                    severity="INFO",
                    confidence=Decimal("1"),
                    recommended_action=(
                        "Review this cited indicator with effective policy and source evidence."
                    ),
                    calculation_ids=tuple(dict.fromkeys(cited_calculations)),
                )
            )

        return AgentOutput(
            agent_name=self.name,
            task_id=request.task_id,
            conclusion=(
                "Repayment-capacity indicators were interpreted only from persisted deterministic "
                "calculation references; no loan approval or rejection was produced."
            ),
            findings=tuple(findings),
            calculations=calculations,
            missing_information=missing,
            risk_flags=tuple(sorted(risk_flags)),
            limitations=(
                "Policy thresholds are evaluated by the policy service, not by the Credit Agent.",
                "The interpretation is decision support only and cannot create a loan decision.",
            ),
            recommended_action=(
                "Complete repayment calculations and source validation before human review."
                if missing
                else "Submit the evidence-backed indicators to policy validation and an authorized reviewer."
            ),
            confidence=Decimal("0.90") if not missing else Decimal("0.40"),
        )


def _repayment_metrics(calculations: Iterable[CalculationReference]) -> dict[str, Decimal]:
    metrics: dict[str, Decimal] = {}
    for calculation in calculations:
        calculation_type = calculation.calculation_type.strip().upper()
        if calculation_type in _REQUIRED_REPAYMENT_METRICS and calculation.result_value is not None:
            metrics[calculation_type] = calculation.result_value
        if calculation_type != "AFFORDABILITY":
            continue
        payload_names = {
            "DTI": "dti",
            "DSCR": "dscr",
            "NET_DISPOSABLE_INCOME": "net_disposable_income",
        }
        for metric, payload_name in payload_names.items():
            parsed = _decimal(calculation.result_payload.get(payload_name))
            if parsed is not None:
                metrics[metric] = parsed
        obligations = _decimal(calculation.inputs.get("existing_obligations"))
        if obligations is not None:
            metrics["EXISTING_MONTHLY_OBLIGATIONS"] = obligations
    return metrics


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, (bool, float)):
        raise TypeError("Persisted financial calculation values must not use bool or binary float")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Persisted financial calculation value is not a decimal") from exc
    if not result.is_finite():
        raise ValueError("Persisted financial calculation value must be finite")
    return result


def _calculation_finding(
    calculations: tuple[CalculationReference, ...],
    *,
    metric: str,
    finding_type: str,
    title: str,
    description: str,
    severity: str,
    action: str,
) -> FindingDraft:
    calculation_ids = tuple(
        dict.fromkeys(
            calculation.calculation_id
            for calculation in calculations
            if _calculation_contains_metric(calculation, metric)
        )
    )
    return FindingDraft(
        finding_type=finding_type,
        title=title,
        description=description,
        severity=severity,
        confidence=Decimal("1"),
        recommended_action=action,
        calculation_ids=calculation_ids,
    )


def _calculation_contains_metric(calculation: CalculationReference, metric: str) -> bool:
    if calculation.calculation_type.strip().upper() == metric:
        return True
    if calculation.calculation_type.strip().upper() != "AFFORDABILITY":
        return False
    if metric == "EXISTING_MONTHLY_OBLIGATIONS":
        return "existing_obligations" in calculation.inputs
    payload_key = {
        "DTI": "dti",
        "DSCR": "dscr",
        "NET_DISPOSABLE_INCOME": "net_disposable_income",
    }.get(metric)
    return payload_key is not None and payload_key in calculation.result_payload
