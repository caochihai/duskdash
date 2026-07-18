"""Application service for one read-only SME Credit Agent."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Awaitable, Callable, Mapping, TypeVar
from uuid import uuid4

from pydantic import ValidationError

from .audit import NullAuditSink, SystemClock
from .card import AGENT_ID, ALLOWED_TOOLS, TOOL_SCOPES
from .errors import (
    AgentDeadlineExceeded,
    PermissionScopeError,
    ToolBudgetExceeded,
    ToolExecutionError,
)
from .models import (
    AgentConfig,
    AgentMetadata,
    AuditEvent,
    CalculationContext,
    CashflowAnalysis,
    CollateralPolicyMode,
    CollateralAnalysis,
    CollateralSnapshotResult,
    CreditAnalysisResultV1,
    CreditFacilitiesResult,
    CreditPolicyResult,
    CreditTaskInputV1,
    Customer360Result,
    DataQuality,
    DatasetQuality,
    Decision,
    Evidence,
    FacilityAnalysis,
    FinancialMetricsResult,
    FinancialStatementsResult,
    FollowUpQuestion,
    FreshnessStatus,
    InfoRequest,
    NextAction,
    PolicyCitation,
    PolicyStatus,
    QualityStatus,
    Recommendation,
    RelationshipAnalysis,
    RepaymentAnalysis,
    RepaymentHistoryResult,
    ResultStatus,
    ToolEnvelope,
    ToolErrorDetail,
    ToolStatus,
    TransactionSummaryResult,
)
from .ports import AuditSink, Clock, CreditTools
from .rules import (
    EV_COLLATERAL,
    EV_CUSTOMER,
    EV_FACILITY,
    EV_FINANCIALS,
    EV_INPUT,
    EV_METRICS,
    EV_POLICY,
    EV_REPAYMENT,
    EV_TRANSACTION,
    Evaluation,
    EvaluationInputs,
    aggregate_quality,
    evaluate_credit_case,
)


ResultModel = TypeVar("ResultModel", bound=ToolEnvelope[Any])


@dataclass(slots=True)
class _RunState:
    run_id: str
    task_id: str | None
    case_id: str | None = None
    customer_id: str | None = None
    as_of_date: date | None = None
    deadline_monotonic: float | None = None
    tool_call_count: int = 0


@dataclass(slots=True)
class _Sources:
    policy: CreditPolicyResult
    customer: Customer360Result
    facilities: CreditFacilitiesResult
    repayment: RepaymentHistoryResult
    transactions: TransactionSummaryResult
    statements: FinancialStatementsResult
    metrics: FinancialMetricsResult | None
    collateral: CollateralSnapshotResult | None


class CreditAgent:
    """A framework-neutral, deterministic Credit Agent application service."""

    __slots__ = ("tools", "clock", "config", "audit_sink", "_controls_locked")

    _CONTROL_FIELDS = frozenset(
        {"tools", "clock", "config", "audit_sink", "_controls_locked"}
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if (
            name in self._CONTROL_FIELDS
            and getattr(self, "_controls_locked", False)
        ):
            raise AttributeError(
                f"CreditAgent control '{name}' is immutable after initialization"
            )
        object.__setattr__(self, name, value)

    def __init__(
        self,
        *,
        tools: CreditTools,
        audit_sink: AuditSink | None = None,
        clock: Clock | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        object.__setattr__(self, "_controls_locked", False)
        self.tools = tools
        self.clock = clock or SystemClock()
        self.config = config or AgentConfig()
        if self.config.require_audit_sink and not self.config.fail_on_audit_error:
            raise ValueError(
                "require_audit_sink=True requires fail_on_audit_error=True"
            )
        if self.config.require_audit_sink and (
            audit_sink is None or not getattr(audit_sink, "durable", False)
        ):
            raise ValueError(
                "require_audit_sink=True requires an AuditSink declaring durable=True"
            )
        self.audit_sink = audit_sink or NullAuditSink()
        object.__setattr__(self, "_controls_locked", True)

    async def run(
        self, task: CreditTaskInputV1 | Mapping[str, Any]
    ) -> CreditAnalysisResultV1:
        """Run one immutable analysis and always return the unified V1 contract."""

        run_id = str(uuid4())
        raw = task if isinstance(task, Mapping) else task.model_dump(mode="python")
        try:
            validated = CreditTaskInputV1.model_validate(task)
        except ValidationError as exc:
            state = _RunState(
                run_id=run_id,
                task_id=self._safe_string(raw.get("task_id")) if isinstance(raw, Mapping) else None,
                case_id=self._safe_string(raw.get("case_id")) if isinstance(raw, Mapping) else None,
                as_of_date=self._safe_date(raw.get("as_of_date")) if isinstance(raw, Mapping) else None,
                deadline_monotonic=self.clock.monotonic() + self.config.timeout_seconds,
            )
            result = self._invalid_input_result(raw, exc, state)
            await self._emit_best_effort(
                state,
                "input_rejected",
                {"missing_or_invalid_field_count": len(result.missing_information)},
            )
            return result

        state = _RunState(
            run_id=run_id,
            task_id=validated.task_id,
            case_id=validated.case_id,
            customer_id=validated.customer_id,
            as_of_date=validated.as_of_date,
            deadline_monotonic=self.clock.monotonic() + self.config.timeout_seconds,
        )
        if self.config.require_audit_sink and not getattr(
            self.audit_sink, "durable", False
        ):
            return self._system_exception_result(
                validated,
                state,
                ToolErrorDetail(
                    code="AUDIT_SINK_CONTROL_FAILURE",
                    message="The required durable audit sink is unavailable.",
                    retryable=False,
                ),
            )
        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                await self._emit(
                    state, "run_started", {"task_type": validated.task_type.value}
                )
                result = await self._run_validated(validated, state)
                await self._emit(
                    state,
                    "result_emitted",
                    {
                        "status": result.status.value,
                        "decision": result.recommendation.decision.value,
                        "tool_call_count": state.tool_call_count,
                    },
                )
                return result
        except TimeoutError:
            result = self._system_exception_result(
                validated,
                state,
                ToolErrorDetail(
                    code="AGENT_DEADLINE_EXCEEDED",
                    message="The absolute Credit Agent deadline elapsed before assessment completed.",
                    retryable=True,
                ),
            )
        except AgentDeadlineExceeded:
            result = self._system_exception_result(
                validated,
                state,
                ToolErrorDetail(
                    code="AGENT_DEADLINE_EXCEEDED",
                    message="The absolute Credit Agent deadline elapsed before assessment completed.",
                    retryable=True,
                ),
            )
        except ToolExecutionError as exc:
            result = self._system_exception_result(
                validated,
                state,
                ToolErrorDetail(
                    code="MANDATORY_TOOL_FAILED",
                    message="A mandatory read tool failed; the case was not assessed.",
                    tool_name=exc.tool_name,
                    retryable=True,
                ),
            )
        except ToolBudgetExceeded:
            result = self._system_exception_result(
                validated,
                state,
                ToolErrorDetail(
                    code="TOOL_BUDGET_EXCEEDED",
                    message="The configured tool-call budget was exceeded.",
                    retryable=False,
                ),
            )
        except PermissionScopeError as exc:
            result = self._system_exception_result(
                validated,
                state,
                ToolErrorDetail(
                    code="MISSING_READ_SCOPE",
                    message="The task lacks required read scopes: " + ", ".join(sorted(exc.missing_scopes)),
                    retryable=False,
                ),
            )
        except Exception as exc:  # Do not leak adapter payloads or sensitive values.
            result = self._system_exception_result(
                validated,
                state,
                ToolErrorDetail(
                    code="INTERNAL_AGENT_ERROR",
                    message="Unexpected internal error; inspect the sanitized audit event.",
                    retryable=False,
                ),
            )
            await self._emit_best_effort(
                state,
                "internal_error",
                {"exception_type": type(exc).__name__},
            )

        await self._emit_best_effort(
            state,
            "result_emitted",
            {
                "status": result.status.value,
                "decision": result.recommendation.decision.value,
                "tool_call_count": state.tool_call_count,
            },
        )
        return result

    async def _run_validated(
        self, task: CreditTaskInputV1, state: _RunState
    ) -> CreditAnalysisResultV1:
        tool_names = {
            "retrieve_credit_policy",
            "get_customer_360",
            "get_credit_facilities",
            "get_repayment_history",
            "get_transaction_summary",
            "get_financial_statements",
            "calculate_financial_metrics",
        }
        if task.credit_request.collateral_required:
            tool_names.add("get_collateral_snapshot")
        missing_scopes = {
            TOOL_SCOPES[name]
            for name in tool_names
            if TOOL_SCOPES[name] not in task.permissions.allowed_scopes
        }
        if missing_scopes:
            raise PermissionScopeError(missing_scopes)

        policy = await self._call_tool(
            state,
            "retrieve_credit_policy",
            lambda: self.tools.retrieve_credit_policy(task),
            CreditPolicyResult,
        )
        if policy.status == ToolStatus.NO_DATA or policy.data is None:
            evidence = [
                *self._policy_evidence(
                    policy,
                    "No applicable credit policy was returned for the locked cutoff date.",
                    primary_claim_id="claim-policy-availability",
                ),
                self._input_evidence(task, state),
            ]
            return self._needs_info_result(
                task,
                state,
                missing=["applicable active credit policy"],
                evidence=evidence,
                questions=[
                    FollowUpQuestion(
                        question="Publish or identify the applicable active credit policy for this task and cutoff date.",
                        why_it_matters="A positive credit recommendation cannot use an absent or assumed policy.",
                        expected_evidence=["active_versioned_credit_policy"],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_POLICY],
                    )
                ],
                summary="No applicable active policy was returned, so the credit request cannot be assessed.",
            )
        if not policy.data.is_active_on(task.as_of_date):
            evidence = [
                *self._policy_evidence(
                    policy,
                    "The returned policy is not active for the locked cutoff date.",
                ),
                self._input_evidence(task, state),
            ]
            return self._needs_info_result(
                task,
                state,
                missing=["policy active on as_of_date"],
                evidence=evidence,
                questions=[
                    FollowUpQuestion(
                        question="Provide a policy version whose effective period covers the locked cutoff date.",
                        why_it_matters="Superseded, expired, draft, or future policy cannot support the assessment.",
                        expected_evidence=["applicable_policy_version"],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_POLICY],
                    )
                ],
                summary="The returned policy is not effective at the analysis cutoff, so no positive recommendation is permitted.",
                policy=policy,
            )

        if policy.data.placeholder_data and not self.config.allow_placeholder_policy:
            return self._system_exception_result(
                task,
                state,
                ToolErrorDetail(
                    code="PLACEHOLDER_POLICY_FORBIDDEN",
                    message=(
                        "The policy source is marked as placeholder data, but this "
                        "agent runtime does not explicitly allow demo policy data."
                    ),
                    tool_name="retrieve_credit_policy",
                    retryable=False,
                ),
            )

        policy_mismatches: list[str] = []
        policy_data = policy.data
        if task.task_type not in policy_data.applicable_task_types:
            policy_mismatches.append("task_type")
        if (
            "*" not in policy_data.applicable_product_codes
            and task.credit_request.product_code
            not in policy_data.applicable_product_codes
        ):
            policy_mismatches.append("product_code")
        if (
            "*" not in policy_data.applicable_currencies
            and task.credit_request.currency not in policy_data.applicable_currencies
        ):
            policy_mismatches.append("currency")
        if (
            policy_data.collateral_mode == CollateralPolicyMode.REQUIRED
            and not task.credit_request.collateral_required
        ):
            policy_mismatches.append("collateral_required")
        if (
            policy_data.collateral_mode == CollateralPolicyMode.NOT_APPLICABLE
            and task.credit_request.collateral_required
        ):
            policy_mismatches.append("collateral_not_applicable")
        if policy_mismatches:
            evidence = [
                self._input_evidence(task, state),
                *self._policy_evidence(
                    policy,
                    self._policy_fact(policy),
                ),
            ]
            return self._needs_info_result(
                task,
                state,
                missing=[
                    "applicable policy match: " + ", ".join(policy_mismatches)
                ],
                evidence=evidence,
                questions=[
                    FollowUpQuestion(
                        question="Provide an active policy matched to the task, product, currency, and collateral mode.",
                        why_it_matters="An active policy for a different product or task cannot govern this case.",
                        expected_evidence=["matched_active_credit_policy"],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_INPUT, EV_POLICY],
                    )
                ],
                summary="The returned active policy is not applicable to the submitted credit task.",
                policy=policy,
            )

        customer = await self._call_tool(
            state,
            "get_customer_360",
            lambda: self.tools.get_customer_360(task),
            Customer360Result,
        )
        if (
            customer.data is not None
            and "*" not in policy_data.applicable_segments
            and customer.data.segment not in policy_data.applicable_segments
        ):
            evidence = [
                self._input_evidence(task, state),
                *self._policy_evidence(
                    policy,
                    self._policy_fact(policy),
                ),
                self._envelope_evidence(
                    EV_CUSTOMER,
                    "claim-customer-segment",
                    customer,
                    self._customer_fact(customer),
                ),
            ]
            return self._needs_info_result(
                task,
                state,
                missing=["applicable policy match: customer segment"],
                evidence=evidence,
                questions=[
                    FollowUpQuestion(
                        question="Provide an active credit policy applicable to the authoritative customer segment.",
                        why_it_matters="A policy for another customer segment cannot govern this case.",
                        expected_evidence=["segment_matched_active_credit_policy"],
                        blocking_if_unanswered=True,
                        evidence_ids=[EV_POLICY, EV_CUSTOMER],
                    )
                ],
                summary="The returned active policy does not apply to the authoritative customer segment.",
                policy=policy,
            )

        calls: list[tuple[str, Awaitable[ToolEnvelope[Any]]]] = [
            (
                "get_credit_facilities",
                self._call_tool(
                    state,
                    "get_credit_facilities",
                    lambda: self.tools.get_credit_facilities(task),
                    CreditFacilitiesResult,
                ),
            ),
            (
                "get_repayment_history",
                self._call_tool(
                    state,
                    "get_repayment_history",
                    lambda: self.tools.get_repayment_history(task),
                    RepaymentHistoryResult,
                ),
            ),
            (
                "get_transaction_summary",
                self._call_tool(
                    state,
                    "get_transaction_summary",
                    lambda: self.tools.get_transaction_summary(task),
                    TransactionSummaryResult,
                ),
            ),
            (
                "get_financial_statements",
                self._call_tool(
                    state,
                    "get_financial_statements",
                    lambda: self.tools.get_financial_statements(task),
                    FinancialStatementsResult,
                ),
            ),
        ]
        if task.credit_request.collateral_required:
            calls.append(
                (
                    "get_collateral_snapshot",
                    self._call_tool(
                        state,
                        "get_collateral_snapshot",
                        lambda: self.tools.get_collateral_snapshot(task),
                        CollateralSnapshotResult,
                    ),
                )
            )
        gathered = await asyncio.gather(
            *(call for _, call in calls), return_exceptions=True
        )
        values: dict[str, ToolEnvelope[Any]] = {"get_customer_360": customer}
        for (name, _), item in zip(calls, gathered, strict=True):
            if isinstance(item, BaseException):
                if isinstance(item, (ToolExecutionError, ToolBudgetExceeded)):
                    raise item
                raise ToolExecutionError(name, type(item).__name__)
            values[name] = item

        statements = FinancialStatementsResult.model_validate(
            values["get_financial_statements"]
        )
        metrics: FinancialMetricsResult | None = None
        if (
            statements.data is not None
            and statements.data.current is not None
            and statements.data.prior is not None
        ):
            facilities_data = values["get_credit_facilities"].data
            transaction_data = values["get_transaction_summary"].data
            context = CalculationContext(
                transaction_summary=transaction_data,
                facilities=facilities_data,
                requested_limit=task.credit_request.requested_limit,
                requested_tenor_months=task.credit_request.requested_tenor_months,
                currency=task.credit_request.currency,
            )
            metrics = await self._call_tool(
                state,
                "calculate_financial_metrics",
                lambda: self.tools.calculate_financial_metrics(task, statements, context),
                FinancialMetricsResult,
            )

        sources = _Sources(
            policy=policy,
            customer=customer,
            facilities=CreditFacilitiesResult.model_validate(values["get_credit_facilities"]),
            repayment=RepaymentHistoryResult.model_validate(values["get_repayment_history"]),
            transactions=TransactionSummaryResult.model_validate(values["get_transaction_summary"]),
            statements=statements,
            metrics=metrics,
            collateral=(
                CollateralSnapshotResult.model_validate(values["get_collateral_snapshot"])
                if task.credit_request.collateral_required
                else None
            ),
        )
        evaluation = evaluate_credit_case(
            EvaluationInputs(
                task=task,
                policy_result=sources.policy,
                customer=sources.customer,
                facilities=sources.facilities,
                repayment=sources.repayment,
                transactions=sources.transactions,
                statements=sources.statements,
                metrics=sources.metrics,
                collateral=sources.collateral,
            ),
            max_questions=self.config.max_follow_up_questions,
        )
        return self._assemble_result(task, state, sources, evaluation)

    async def _call_tool(
        self,
        state: _RunState,
        tool_name: str,
        call: Callable[[], Awaitable[Any]],
        result_model: type[ResultModel],
    ) -> ResultModel:
        if tool_name not in ALLOWED_TOOLS:
            raise ToolExecutionError(tool_name, "Tool is not in the Agent Card allowlist")
        if state.tool_call_count >= self.config.max_tool_calls:
            raise ToolBudgetExceeded()
        state.tool_call_count += 1
        started = self.clock.monotonic()
        await self._emit(state, "tool_started", {"tool_name": tool_name})
        try:
            raw = await asyncio.wait_for(call(), self.config.per_tool_timeout_seconds)
            result = result_model.model_validate(raw)
        except TimeoutError as exc:
            await self._emit_best_effort(
                state, "tool_failed", {"tool_name": tool_name, "reason": "timeout"}
            )
            raise ToolExecutionError(tool_name, "timeout") from exc
        except ValidationError as exc:
            await self._emit_best_effort(
                state,
                "tool_failed",
                {"tool_name": tool_name, "reason": "invalid_contract"},
            )
            raise ToolExecutionError(tool_name, "invalid response contract") from exc
        except Exception as exc:
            await self._emit_best_effort(
                state,
                "tool_failed",
                {"tool_name": tool_name, "reason": type(exc).__name__},
            )
            raise ToolExecutionError(tool_name, "adapter execution failed") from exc
        if result.status in {ToolStatus.ERROR, ToolStatus.TIMEOUT, ToolStatus.FORBIDDEN}:
            await self._emit_best_effort(
                state,
                "tool_failed",
                {"tool_name": tool_name, "reason": result.status.value},
            )
            raise ToolExecutionError(tool_name, result.status.value)
        if (
            result.tool_name != tool_name
            or result.task_id != state.task_id
            or result.case_id != state.case_id
            or result.customer_id != state.customer_id
            or result.as_of_date != state.as_of_date
        ):
            await self._emit_best_effort(
                state,
                "tool_failed",
                {"tool_name": tool_name, "reason": "context_binding_mismatch"},
            )
            raise ToolExecutionError(tool_name, "response context binding mismatch")
        elapsed_ms = round((self.clock.monotonic() - started) * 1000, 3)
        await self._emit(
            state,
            "tool_succeeded",
            {
                "tool_name": tool_name,
                "tool_run_id": result.tool_run_id,
                "status": result.status.value,
                "latency_ms": elapsed_ms,
            },
        )
        return result

    def _assemble_result(
        self,
        task: CreditTaskInputV1,
        state: _RunState,
        sources: _Sources,
        evaluation: Evaluation,
    ) -> CreditAnalysisResultV1:
        evidence = self._build_evidence(task, state, sources)
        evidence_ids = {item.evidence_id for item in evidence}

        policy_citations = self._policy_citations(sources.policy)
        overall, freshness = aggregate_quality(evaluation.datasets.values())
        expected_evidence = 8 if task.credit_request.collateral_required else 7
        canonical_source_evidence = {
            EV_POLICY,
            EV_CUSTOMER,
            EV_FACILITY,
            EV_REPAYMENT,
            EV_TRANSACTION,
            EV_FINANCIALS,
            EV_METRICS,
        }
        if task.credit_request.collateral_required:
            canonical_source_evidence.add(EV_COLLATERAL)
        available_evidence = sum(
            1
            for item in evidence
            if item.evidence_id in canonical_source_evidence
            and item.fact.find("NO_DATA") == -1
        )
        coverage = min(
            Decimal("1"), Decimal(available_evidence) / Decimal(expected_evidence)
        )
        data_quality = DataQuality(
            overall_status=overall,
            evidence_coverage=coverage,
            freshness_status=freshness,
            conflicts_detected=len(evaluation.conflicts),
            datasets=evaluation.datasets,
            conflicts=evaluation.conflicts,
        )

        recommendation_evidence = self._recommendation_evidence(
            evaluation, evidence_ids
        )
        decision = evaluation.decision
        recommended_limit = (
            task.credit_request.requested_limit
            if decision
            in {Decision.READY_FOR_APPROVAL_REVIEW, Decision.PASS_WITH_CONDITIONS}
            else None
        )
        recommended_tenor = (
            task.credit_request.requested_tenor_months
            if recommended_limit is not None
            else None
        )
        recommendation = Recommendation(
            decision=decision,
            recommended_limit=recommended_limit,
            recommended_tenor_months=recommended_tenor,
            currency=task.credit_request.currency if recommended_limit is not None else None,
            summary=self._summary(decision, sources.policy.data.placeholder_data),
            evidence_ids=recommendation_evidence,
        )
        status = (
            ResultStatus.NEEDS_INFO
            if decision == Decision.NEEDS_INFO
            else ResultStatus.COMPLETED
        )

        next_actions = [
            NextAction(
                action="Validate formulas, evidence, policy citations, and recommendation independently.",
                target_agent="validation_agent",
                mode=None,
                evidence_ids=recommendation_evidence,
            )
        ]
        if decision == Decision.NEEDS_INFO:
            next_actions.append(
                NextAction(
                    action="Request the listed missing evidence and create a fresh Credit Agent run.",
                    target_agent="supervisor_agent",
                    evidence_ids=recommendation_evidence,
                )
            )
        return CreditAnalysisResultV1(
            agent=self._agent_metadata(state),
            task_id=task.task_id,
            case_id=task.case_id,
            as_of_date=task.as_of_date,
            status=status,
            recommendation=recommendation,
            relationship_analysis=self._relationship_analysis(sources),
            facility_analysis=self._facility_analysis(sources),
            repayment_analysis=self._repayment_analysis(sources),
            cashflow_analysis=self._cashflow_analysis(sources),
            financial_metrics=None if sources.metrics is None else sources.metrics.data,
            collateral_analysis=self._collateral_analysis(sources),
            risk_flags=evaluation.risk_flags,
            conditions=evaluation.conditions,
            missing_information=evaluation.missing_information,
            follow_up_questions=evaluation.follow_up_questions,
            policy_citations=policy_citations,
            evidence=evidence,
            data_quality=data_quality,
            next_actions=next_actions,
            info_requests=evaluation.info_requests,
            errors=[],
            tool_call_count=state.tool_call_count,
        )

    def _build_evidence(
        self, task: CreditTaskInputV1, state: _RunState, sources: _Sources
    ) -> list[Evidence]:
        items = [self._input_evidence(task, state)]
        items.extend(
            self._policy_evidence(
                sources.policy,
                self._policy_fact(sources.policy),
            )
        )
        items.append(
            self._envelope_evidence(
                EV_CUSTOMER,
                "claim-relationship",
                sources.customer,
                self._customer_fact(sources.customer),
            )
        )
        items.append(
            self._envelope_evidence(
                EV_FACILITY,
                "claim-facility",
                sources.facilities,
                self._facility_fact(sources.facilities),
            )
        )
        items.append(
            self._envelope_evidence(
                EV_REPAYMENT,
                "claim-repayment",
                sources.repayment,
                self._repayment_fact(sources.repayment),
            )
        )
        items.append(
            self._envelope_evidence(
                EV_TRANSACTION,
                "claim-cashflow",
                sources.transactions,
                self._transaction_fact(sources.transactions),
            )
        )
        items.append(
            self._envelope_evidence(
                EV_FINANCIALS,
                "claim-financial-statements",
                sources.statements,
                self._statements_fact(sources.statements),
            )
        )
        if sources.metrics is not None:
            items.append(
                self._envelope_evidence(
                    EV_METRICS,
                    "claim-financial-metrics",
                    sources.metrics,
                    self._metrics_fact(sources.metrics),
                )
            )
        if sources.collateral is not None:
            items.append(
                self._envelope_evidence(
                    EV_COLLATERAL,
                    "claim-collateral",
                    sources.collateral,
                    self._collateral_fact(sources.collateral),
                )
            )
        return items

    def _policy_evidence(
        self,
        result: CreditPolicyResult,
        primary_fact: str,
        *,
        primary_claim_id: str = "claim-policy",
    ) -> list[Evidence]:
        """Resolve every cited policy claim without exposing full policy text."""

        items = [
            self._envelope_evidence(
                EV_POLICY,
                primary_claim_id,
                result,
                primary_fact,
            )
        ]
        data = result.data
        if data is None:
            return items

        seen_claims = {primary_claim_id}
        for clause in data.clauses:
            for claim_id in sorted(clause.claim_ids):
                if claim_id in seen_claims:
                    continue
                seen_claims.add(claim_id)
                items.append(
                    self._envelope_evidence(
                        f"{EV_POLICY}-claim-{len(items):03d}",
                        claim_id,
                        result,
                        (
                            f"Policy {data.document_id} version {data.version}, "
                            f"section {clause.section}, was returned for the locked cutoff."
                        ),
                    )
                )
        return items

    @staticmethod
    def _input_evidence(task: CreditTaskInputV1, state: _RunState) -> Evidence:
        request = task.credit_request
        return Evidence(
            evidence_id=EV_INPUT,
            claim_id="claim-request",
            source_system="supervisor",
            source_reference=task.case_id,
            as_of_date=task.as_of_date,
            fact=(
                f"Requested limit={request.requested_limit} {request.currency}; "
                f"tenor={request.requested_tenor_months} months; "
                f"current limit={request.current_limit} {request.currency}."
            ),
            tool_run_id=f"validated-input:{state.run_id}",
        )

    @staticmethod
    def _envelope_evidence(
        evidence_id: str,
        claim_id: str,
        result: ToolEnvelope[Any],
        fact: str,
    ) -> Evidence:
        return Evidence(
            evidence_id=evidence_id,
            claim_id=claim_id,
            source_system=result.source_system,
            source_reference=(
                "opaque-"
                + hashlib.sha256(
                    f"{result.tool_run_id}:{result.source_reference}".encode("utf-8")
                ).hexdigest()[:24]
            ),
            as_of_date=result.as_of_date,
            fact=fact,
            tool_run_id=result.tool_run_id,
        )

    @staticmethod
    def _fact_or_status(result: ToolEnvelope[Any], fact: str) -> str:
        if result.data is None:
            return f"Tool status={result.status.value}; no dataset was returned."
        return fact

    def _policy_fact(self, result: CreditPolicyResult) -> str:
        data = result.data
        return self._fact_or_status(
            result,
            "" if data is None else (
                f"Policy document={data.document_id}; version={data.version}; "
                f"status={data.status.value}; effective_from={data.effective_from.isoformat()}; "
                f"effective_to={data.effective_to.isoformat() if data.effective_to else 'open'}."
            ),
        )

    def _customer_fact(self, result: Customer360Result) -> str:
        data = result.data
        return self._fact_or_status(
            result,
            "" if data is None else (
                f"Years with bank={data.years_with_bank}; rating={data.internal_rating}; "
                f"total outstanding={data.total_outstanding} {data.currency}; "
                f"average deposit balance={data.average_deposit_balance} {data.currency}."
            ),
        )

    def _facility_fact(self, result: CreditFacilitiesResult) -> str:
        data = result.data
        return self._fact_or_status(
            result,
            "" if data is None else (
                f"Approved limit={data.approved_limit} {data.currency}; outstanding={data.outstanding} "
                f"{data.currency}; utilization ratio={data.utilization_ratio}; "
                f"ledger_as_of={data.ledger_as_of.isoformat()}."
            ),
        )

    def _repayment_fact(self, result: RepaymentHistoryResult) -> str:
        data = result.data
        return self._fact_or_status(
            result,
            "" if data is None else (
                f"Lookback={data.lookback_months} months; late payments={data.late_payment_count}; "
                f"max DPD={data.max_days_past_due}; current DPD={data.current_days_past_due}; "
                f"restructured debt={data.restructured_debt}."
            ),
        )

    def _transaction_fact(self, result: TransactionSummaryResult) -> str:
        data = result.data
        return self._fact_or_status(
            result,
            "" if data is None else (
                f"Average monthly inflow={data.average_monthly_inflow} {data.currency}; "
                f"average monthly outflow={data.average_monthly_outflow} {data.currency}; "
                f"inflow volatility={data.inflow_volatility}; largest counterparty share="
                f"{data.largest_counterparty_share}; coverage={data.coverage_months} months; "
                f"related-party indicator={data.related_party_flow}."
            ),
        )

    def _statements_fact(self, result: FinancialStatementsResult) -> str:
        data = result.data
        if data is None:
            return self._fact_or_status(result, "")
        current = data.current
        prior = data.prior
        return (
            "Current period="
            + ("missing" if current is None else current.period_end.isoformat())
            + "; prior period="
            + ("missing" if prior is None else prior.period_end.isoformat())
            + (
                ""
                if current is None or prior is None
                else (
                    f"; audit status: current={'audited' if current.audited else 'unaudited'}, "
                    f"prior={'audited' if prior.audited else 'unaudited'}"
                )
            )
            + (
                ""
                if current is None
                else (
                    f"; revenue={current.revenue} {current.currency}; net profit={current.net_profit} "
                    f"{current.currency}; operating cash flow={current.operating_cash_flow} {current.currency}."
                )
            )
        )

    def _metrics_fact(self, result: FinancialMetricsResult) -> str:
        data = result.data
        if data is None:
            return self._fact_or_status(result, "")
        values = ", ".join(
            f"{name}={metric.current} {metric.unit}"
            for name, metric in sorted(data.metrics.items())
        )
        return f"Formula version={data.formula_version}; {values}."

    def _collateral_fact(self, result: CollateralSnapshotResult) -> str:
        data = result.data
        return self._fact_or_status(
            result,
            "" if data is None else (
                f"Eligible value={data.eligible_value} {data.currency}; coverage ratio="
                f"{data.coverage_ratio}; valuation date={data.valuation_date.isoformat()}; "
                f"status={data.valuation_status}; basis={data.coverage_basis}."
            ),
        )

    @staticmethod
    def _policy_citations(result: CreditPolicyResult) -> list[PolicyCitation]:
        data = result.data
        if data is None:
            return []
        return [
            PolicyCitation(
                document_id=data.document_id,
                version=data.version,
                section=clause.section,
                effective_from=data.effective_from,
                effective_to=data.effective_to,
                status=data.status,
                claim_ids=sorted(clause.claim_ids),
            )
            for clause in data.clauses
        ]

    @staticmethod
    def _relationship_analysis(sources: _Sources) -> RelationshipAnalysis | None:
        data = sources.customer.data
        if data is None:
            return None
        return RelationshipAnalysis(
            years_with_bank=data.years_with_bank,
            internal_rating=data.internal_rating,
            relationship_status=data.relationship_status,
            evidence_ids=[EV_CUSTOMER],
        )

    @staticmethod
    def _facility_analysis(sources: _Sources) -> FacilityAnalysis | None:
        data = sources.facilities.data
        if data is None:
            return None
        return FacilityAnalysis(
            current_limit=data.approved_limit,
            outstanding=data.outstanding,
            utilization_ratio=data.utilization_ratio,
            currency=data.currency,
            evidence_ids=[EV_FACILITY],
        )

    @staticmethod
    def _repayment_analysis(sources: _Sources) -> RepaymentAnalysis | None:
        data = sources.repayment.data
        if data is None:
            return None
        assessment = (
            "Returned history contains repayment exceptions; see risk flags."
            if data.late_payment_count or data.restructured_debt or data.current_days_past_due
            else "Returned lookback contains no late payment, current DPD, or restructuring indicator."
        )
        return RepaymentAnalysis(
            lookback_months=data.lookback_months,
            late_payment_count=data.late_payment_count,
            max_days_past_due=data.max_days_past_due,
            current_days_past_due=data.current_days_past_due,
            restructured_debt=data.restructured_debt,
            assessment=assessment,
            evidence_ids=[EV_REPAYMENT],
        )

    @staticmethod
    def _cashflow_analysis(sources: _Sources) -> CashflowAnalysis | None:
        data = sources.transactions.data
        if data is None:
            return None
        return CashflowAnalysis(
            average_monthly_inflow=data.average_monthly_inflow,
            average_monthly_outflow=data.average_monthly_outflow,
            inflow_volatility=data.inflow_volatility,
            largest_counterparty_share=data.largest_counterparty_share,
            currency=data.currency,
            assessment="Cash-flow figures reflect the returned aggregate coverage window.",
            evidence_ids=[EV_TRANSACTION],
        )

    @staticmethod
    def _collateral_analysis(sources: _Sources) -> CollateralAnalysis | None:
        if sources.collateral is None or sources.collateral.data is None:
            return None
        data = sources.collateral.data
        return CollateralAnalysis(
            eligible_value=data.eligible_value,
            coverage_ratio=data.coverage_ratio,
            valuation_status=data.valuation_status,
            currency=data.currency,
            evidence_ids=[EV_COLLATERAL],
        )

    @staticmethod
    def _recommendation_evidence(
        evaluation: Evaluation, known: set[str]
    ) -> list[str]:
        selected: list[str] = [EV_INPUT, EV_POLICY]
        for flag in evaluation.risk_flags:
            selected.extend(flag.evidence_ids)
        for condition in evaluation.conditions:
            selected.extend(condition.evidence_ids)
        for conflict in evaluation.conflicts:
            selected.extend(conflict.evidence_ids)
        for question in evaluation.follow_up_questions:
            selected.extend(question.evidence_ids)
        for message in evaluation.info_requests:
            selected.extend(message.evidence_ids)
        if evaluation.decision in {
            Decision.READY_FOR_APPROVAL_REVIEW,
            Decision.PASS_WITH_CONDITIONS,
            Decision.NOT_RECOMMENDED,
        }:
            selected.extend(
                [
                    EV_CUSTOMER,
                    EV_FACILITY,
                    EV_REPAYMENT,
                    EV_TRANSACTION,
                    EV_FINANCIALS,
                    EV_METRICS,
                    EV_COLLATERAL,
                ]
            )
        if evaluation.decision == Decision.MANUAL_REVIEW and not evaluation.conflicts:
            selected.extend(EV_TRANSACTION for _ in evaluation.info_requests)
        return list(dict.fromkeys(item for item in selected if item in known))

    @staticmethod
    def _summary(decision: Decision, placeholder_policy: bool) -> str:
        suffix = " The applicable policy source is marked as MVP placeholder data." if placeholder_policy else ""
        summaries = {
            Decision.READY_FOR_APPROVAL_REVIEW: "Current and prior-period evidence is complete, policy checks pass, and no blocking conflict was identified.",
            Decision.PASS_WITH_CONDITIONS: "The evidence supports forwarding the case only with the listed, evidence-linked conditions.",
            Decision.NEEDS_INFO: "Mandatory data, policy parameters, or computable metrics are missing; no positive recommendation is made.",
            Decision.MANUAL_REVIEW: "Material conflict or an out-of-scope pattern requires human or specialist review; the agent did not choose between conflicting sources.",
            Decision.NOT_RECOMMENDED: "Complete evidence triggers an active-policy decline treatment for the request.",
            Decision.SYSTEM_EXCEPTION: "A mandatory dependency failed, so the case was not assessed.",
        }
        return summaries[decision] + suffix

    def _needs_info_result(
        self,
        task: CreditTaskInputV1,
        state: _RunState,
        *,
        missing: list[str],
        evidence: list[Evidence],
        questions: list[FollowUpQuestion],
        summary: str,
        policy: CreditPolicyResult | None = None,
    ) -> CreditAnalysisResultV1:
        datasets = {
            "policy": DatasetQuality(
                status=QualityStatus.BLOCKED,
                freshness=FreshnessStatus.UNKNOWN,
                details=missing,
            )
        }
        return CreditAnalysisResultV1(
            agent=self._agent_metadata(state),
            task_id=task.task_id,
            case_id=task.case_id,
            as_of_date=task.as_of_date,
            status=ResultStatus.NEEDS_INFO,
            recommendation=Recommendation(
                decision=Decision.NEEDS_INFO,
                summary=summary,
                evidence_ids=[item.evidence_id for item in evidence],
            ),
            missing_information=missing,
            follow_up_questions=questions[: self.config.max_follow_up_questions],
            policy_citations=[] if policy is None else self._policy_citations(policy),
            evidence=evidence,
            data_quality=DataQuality(
                overall_status=QualityStatus.BLOCKED,
                evidence_coverage=Decimal("0"),
                freshness_status=FreshnessStatus.UNKNOWN,
                conflicts_detected=0,
                datasets=datasets,
            ),
            next_actions=[
                NextAction(
                    action="Validate the NEEDS_INFO result and its policy evidence.",
                    target_agent="validation_agent",
                    evidence_ids=[item.evidence_id for item in evidence],
                ),
                NextAction(
                    action="Provide the missing policy evidence and create a fresh analysis run.",
                    target_agent="supervisor_agent",
                    evidence_ids=[item.evidence_id for item in evidence],
                )
            ],
            tool_call_count=state.tool_call_count,
        )

    def _invalid_input_result(
        self,
        raw: Mapping[str, Any],
        exc: ValidationError,
        state: _RunState,
    ) -> CreditAnalysisResultV1:
        items = []
        for error in exc.errors(include_url=False, include_input=False):
            path = ".".join(str(part) for part in error["loc"])
            items.append(f"{path}: {error['msg']}")
        as_of = self._safe_date(raw.get("as_of_date"))
        return CreditAnalysisResultV1(
            agent=self._agent_metadata(state),
            task_id=self._safe_string(raw.get("task_id")),
            case_id=self._safe_string(raw.get("case_id")),
            as_of_date=as_of,
            status=ResultStatus.NEEDS_INFO,
            recommendation=Recommendation(
                decision=Decision.NEEDS_INFO,
                summary="The task contract is missing required fields or contains invalid values; no tool was called.",
            ),
            missing_information=items,
            follow_up_questions=[
                FollowUpQuestion(
                    question="Provide a valid CreditTaskInputV1 containing every listed missing or invalid field.",
                    why_it_matters="The agent must lock amount, tenor, purpose, scope, and cutoff before reading data.",
                    expected_evidence=["corrected_credit_task_input"],
                    blocking_if_unanswered=True,
                )
            ],
            data_quality=DataQuality(
                overall_status=QualityStatus.NOT_ASSESSED,
                evidence_coverage=Decimal("0"),
                freshness_status=FreshnessStatus.UNKNOWN,
                conflicts_detected=0,
            ),
            next_actions=[
                NextAction(
                    action="Correct the task contract and submit a fresh run.",
                    target_agent="supervisor_agent",
                )
            ],
            tool_call_count=0,
        )

    def _system_exception_result(
        self,
        task: CreditTaskInputV1,
        state: _RunState,
        error: ToolErrorDetail,
    ) -> CreditAnalysisResultV1:
        return CreditAnalysisResultV1(
            agent=self._agent_metadata(state),
            task_id=task.task_id,
            case_id=task.case_id,
            as_of_date=task.as_of_date,
            status=ResultStatus.SYSTEM_EXCEPTION,
            recommendation=Recommendation(
                decision=Decision.SYSTEM_EXCEPTION,
                summary="A mandatory dependency or control failed, so the case was not assessed and no risk conclusion was made.",
            ),
            data_quality=DataQuality(
                overall_status=QualityStatus.NOT_ASSESSED,
                evidence_coverage=Decimal("0"),
                freshness_status=FreshnessStatus.UNKNOWN,
                conflicts_detected=0,
            ),
            next_actions=[
                NextAction(
                    action="Validate the SYSTEM_EXCEPTION result and named control failure.",
                    target_agent="validation_agent",
                ),
                NextAction(
                    action="Resolve the named dependency/control failure and submit a fresh run.",
                    target_agent="supervisor_agent",
                )
            ],
            errors=[error],
            tool_call_count=state.tool_call_count,
        )

    def _agent_metadata(self, state: _RunState) -> AgentMetadata:
        return AgentMetadata(
            agent_id=AGENT_ID,
            agent_version=self.config.agent_version,
            run_id=state.run_id,
        )

    async def _emit(
        self, state: _RunState, event_type: str, details: dict[str, Any]
    ) -> None:
        try:
            timeout = self.config.audit_timeout_seconds
            if state.deadline_monotonic is not None:
                remaining = state.deadline_monotonic - self.clock.monotonic()
                if remaining <= 0:
                    raise AgentDeadlineExceeded()
                timeout = min(timeout, remaining)
            await asyncio.wait_for(
                self.audit_sink.emit(
                    AuditEvent(
                        event_type=event_type,
                        run_id=state.run_id,
                        task_id=state.task_id,
                        occurred_at=self.clock.now(),
                        details=details,
                    )
                ),
                timeout=timeout,
            )
        except Exception:
            if self.config.fail_on_audit_error:
                raise

    async def _emit_best_effort(
        self, state: _RunState, event_type: str, details: dict[str, Any]
    ) -> None:
        try:
            await self._emit(state, event_type, details)
        except Exception:
            return

    @staticmethod
    def _safe_string(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized if normalized and len(normalized) <= 128 else None

    @staticmethod
    def _safe_date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None
