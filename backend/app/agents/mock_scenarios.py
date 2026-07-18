"""Deterministic synthetic inputs for exercising the multi-agent analysis design.

The records in this module are deliberately fictional.  They are application-test
fixtures, not database seed rows, and must never be presented as customer facts.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict

from app.agents.base import AgentInput, EvidenceReference, EvidenceRole
from app.services.multi_agent_analysis_service import MultiAgentAnalysisRequest

_MOCK_NAMESPACE = UUID("6a8c799b-b57a-5dc0-8dc4-4ca784b462da")


class _MockScenarioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MockScenarioCode(StrEnum):
    READY = "READY"
    INCOMPLETE = "INCOMPLETE"


class MockScenarioSummary(_MockScenarioModel):
    scenario_code: MockScenarioCode
    title: str
    description: str
    expected_report_status: Literal["DRAFT", "INCOMPLETE"]
    synthetic_data: Literal[True] = True


class MockAnalysisRequestBundle(_MockScenarioModel):
    summary: MockScenarioSummary
    objective: str
    customer_id: UUID
    loan_application_id: UUID
    analysis_case_id: UUID
    request: MultiAgentAnalysisRequest


_SCENARIOS = (
    MockScenarioSummary(
        scenario_code=MockScenarioCode.READY,
        title="Hồ sơ mô phỏng đủ điều kiện tổng hợp",
        description=(
            "DỮ LIỆU MÔ PHỎNG: hồ sơ có đủ tài liệu, phép tính deterministic và điều khoản "
            "chính sách đã dẫn nguồn. Kết quả chỉ là báo cáo nháp để con người xem xét."
        ),
        expected_report_status="DRAFT",
    ),
    MockScenarioSummary(
        scenario_code=MockScenarioCode.INCOMPLETE,
        title="Hồ sơ mô phỏng thiếu và mâu thuẫn",
        description=(
            "DỮ LIỆU MÔ PHỎNG: hồ sơ có trang tài liệu thiếu, tín hiệu dấu chưa xác nhận, "
            "mâu thuẫn thu nhập và thiếu một phép tính bắt buộc."
        ),
        expected_report_status="INCOMPLETE",
    ),
)


def list_mock_scenarios() -> tuple[MockScenarioSummary, ...]:
    """Return the immutable catalog exposed by the simulation application service."""

    return _SCENARIOS


def build_mock_analysis_request(
    scenario_code: MockScenarioCode | str,
    *,
    objective: str,
    customer_id: UUID | None = None,
    loan_application_id: UUID | None = None,
) -> MockAnalysisRequestBundle:
    """Build one deterministic, fully synthetic multi-agent request.

    Supplying customer/loan IDs only scopes the simulation to a caller-authorized
    context.  All expert facts, documents, calculations and policy records remain
    synthetic and are generated in memory.
    """

    code = _scenario_code(scenario_code)
    normalized_objective = " ".join(objective.split())
    if not normalized_objective:
        raise ValueError("objective must not be empty")

    scoped_customer_id = customer_id or _catalog_uuid(code, "customer")
    scoped_loan_id = loan_application_id or _catalog_uuid(code, "loan-application")
    analysis_case_id = uuid5(
        _MOCK_NAMESPACE,
        (
            f"analysis:{code.value}:{scoped_customer_id}:{scoped_loan_id}:"
            f"{normalized_objective.casefold()}"
        ),
    )
    if code is MockScenarioCode.READY:
        request = _ready_request(
            analysis_case_id=analysis_case_id,
            customer_id=scoped_customer_id,
            loan_application_id=scoped_loan_id,
            objective=normalized_objective,
        )
    else:
        request = _incomplete_request(
            analysis_case_id=analysis_case_id,
            customer_id=scoped_customer_id,
            loan_application_id=scoped_loan_id,
            objective=normalized_objective,
        )
    return MockAnalysisRequestBundle(
        summary=_summary(code),
        objective=normalized_objective,
        customer_id=scoped_customer_id,
        loan_application_id=scoped_loan_id,
        analysis_case_id=analysis_case_id,
        request=request,
    )


def _ready_request(
    *,
    analysis_case_id: UUID,
    customer_id: UUID,
    loan_application_id: UUID,
    objective: str,
) -> MultiAgentAnalysisRequest:
    identity_document_id = _run_uuid(analysis_case_id, "document:identity")
    salary_document_id = _run_uuid(analysis_case_id, "document:salary-slip")
    statement_document_id = _run_uuid(analysis_case_id, "document:account-statement")
    source_ids = frozenset(
        {identity_document_id, salary_document_id, statement_document_id}
    )
    evidence = [
        _document_evidence(
            source_id=identity_document_id,
            document_type="IDENTITY_DOCUMENT",
            field_name="synthetic_case_reference",
            quoted_text="Synthetic case reference ALPHA is recorded.",
        ),
        _document_evidence(
            source_id=salary_document_id,
            document_type="SALARY_SLIP",
            field_name="monthly_income",
            quoted_text="Synthetic verified monthly income: 30000000.0000 VND.",
        ),
        _document_evidence(
            source_id=statement_document_id,
            document_type="ACCOUNT_STATEMENT",
            field_name="average_salary_inflow",
            quoted_text="Synthetic average salary inflow: 30000000.0000 VND.",
        ),
    ]
    documents = [
        _document(
            source_id=identity_document_id,
            document_type="IDENTITY_DOCUMENT",
            fields={"synthetic_case_reference": "ALPHA"},
        ),
        _document(
            source_id=salary_document_id,
            document_type="SALARY_SLIP",
            fields={
                "synthetic_case_reference": "ALPHA",
                "monthly_income": "30000000.0000",
            },
            presence_indicators={"signature": True, "stamp": True},
        ),
        _document(
            source_id=statement_document_id,
            document_type="ACCOUNT_STATEMENT",
            fields={
                "synthetic_case_reference": "ALPHA",
                "average_salary_inflow": "30000000.0000",
            },
        ),
    ]
    calculation_ids = {
        name: _run_uuid(analysis_case_id, f"calculation:{name}")
        for name in (
            "dti",
            "dscr",
            "net-disposable-income",
            "existing-monthly-obligations",
        )
    }
    calculations = [
        _calculation(
            calculation_id=calculation_ids["dti"],
            calculation_type="DTI",
            inputs={
                "accepted_monthly_income": Decimal("30000000.0000"),
                "total_monthly_debt_service": Decimal("12000000.0000"),
            },
            result_value=Decimal("0.40000000"),
            unit="RATIO",
        ),
        _calculation(
            calculation_id=calculation_ids["dscr"],
            calculation_type="DSCR",
            inputs={
                "accepted_monthly_income": Decimal("30000000.0000"),
                "total_monthly_debt_service": Decimal("12000000.0000"),
            },
            result_value=Decimal("2.50000000"),
            unit="RATIO",
        ),
        _calculation(
            calculation_id=calculation_ids["net-disposable-income"],
            calculation_type="NET_DISPOSABLE_INCOME",
            inputs={
                "accepted_monthly_income": Decimal("30000000.0000"),
                "total_monthly_debt_service": Decimal("12000000.0000"),
            },
            result_value=Decimal("18000000.0000"),
            unit="VND",
        ),
        _calculation(
            calculation_id=calculation_ids["existing-monthly-obligations"],
            calculation_type="EXISTING_MONTHLY_OBLIGATIONS",
            inputs={"verified_existing_obligations": Decimal("6000000.0000")},
            result_value=Decimal("6000000.0000"),
            unit="VND",
        ),
    ]
    policy = _policy_context(
        analysis_case_id,
        status="CONDITIONAL",
        rule_code="HUMAN_REVIEW_REQUIRED",
        explanation=(
            "The effective synthetic policy requires an authorized human to review cited evidence "
            "before any official decision."
        ),
    )
    shared = _shared_input_fields(
        analysis_case_id=analysis_case_id,
        customer_id=customer_id,
        loan_application_id=loan_application_id,
        authorized_source_ids=source_ids,
    )
    return MultiAgentAnalysisRequest(
        document_input=AgentInput(
            task_id=_run_uuid(analysis_case_id, "task:document"),
            **shared,
            context={
                "objective": objective,
                "assessment_date": "2026-07-18",
                "required_document_types": [
                    "IDENTITY_DOCUMENT",
                    "SALARY_SLIP",
                    "ACCOUNT_STATEMENT",
                ],
                "required_document_indicators": {
                    "SALARY_SLIP": ["signature", "stamp"]
                },
                "documents": documents,
                "evidence": evidence,
            },
        ),
        credit_input=AgentInput(
            task_id=_run_uuid(analysis_case_id, "task:credit"),
            **shared,
            context={"objective": objective, "calculations": calculations},
        ),
        compliance_input=AgentInput(
            task_id=_run_uuid(analysis_case_id, "task:compliance"),
            **shared,
            context={"objective": objective, **policy["context"]},
        ),
        authorized_source_ids=source_ids,
        valid_calculation_ids=frozenset(calculation_ids.values()),
        valid_policy_clause_ids=frozenset({policy["clause_id"]}),
    )


def _incomplete_request(
    *,
    analysis_case_id: UUID,
    customer_id: UUID,
    loan_application_id: UUID,
    objective: str,
) -> MultiAgentAnalysisRequest:
    identity_document_id = _run_uuid(analysis_case_id, "document:identity")
    salary_document_id = _run_uuid(analysis_case_id, "document:salary-slip")
    employment_document_id = _run_uuid(analysis_case_id, "document:employment-confirmation")
    statement_document_id = _run_uuid(analysis_case_id, "document:account-statement")
    source_ids = frozenset(
        {
            identity_document_id,
            salary_document_id,
            employment_document_id,
            statement_document_id,
        }
    )
    evidence = [
        _document_evidence(
            source_id=identity_document_id,
            document_type="IDENTITY_DOCUMENT",
            field_name="synthetic_case_reference",
            quoted_text="Synthetic case reference BETA is recorded.",
        ),
        _document_evidence(
            source_id=salary_document_id,
            document_type="SALARY_SLIP",
            field_name="monthly_income",
            quoted_text="Synthetic salary slip income: 30000000.0000 VND.",
        ),
        _document_evidence(
            source_id=employment_document_id,
            document_type="EMPLOYMENT_CONFIRMATION",
            field_name="monthly_income",
            quoted_text="Synthetic employment confirmation income: 22000000.0000 VND.",
        ),
        _document_evidence(
            source_id=statement_document_id,
            document_type="ACCOUNT_STATEMENT",
            field_name="monthly_income",
            quoted_text="Synthetic account statement income: 20000000.0000 VND.",
        ),
    ]
    documents = [
        _document(
            source_id=identity_document_id,
            document_type="IDENTITY_DOCUMENT",
            fields={"synthetic_case_reference": "BETA"},
        ),
        _document(
            source_id=salary_document_id,
            document_type="SALARY_SLIP",
            fields={"synthetic_case_reference": "BETA", "monthly_income": "30000000.0000"},
            presence_indicators={"signature": True, "stamp": True},
        ),
        _document(
            source_id=employment_document_id,
            document_type="EMPLOYMENT_CONFIRMATION",
            fields={"synthetic_case_reference": "BETA", "monthly_income": "22000000.0000"},
            presence_indicators={"signature": True, "stamp": False},
        ),
        _document(
            source_id=statement_document_id,
            document_type="ACCOUNT_STATEMENT",
            fields={"synthetic_case_reference": "BETA", "monthly_income": "20000000.0000"},
            verification_status="PENDING_REVIEW",
        ),
    ]
    calculation_ids = {
        name: _run_uuid(analysis_case_id, f"calculation:{name}")
        for name in ("dti", "net-disposable-income", "existing-monthly-obligations")
    }
    calculations = [
        _calculation(
            calculation_id=calculation_ids["dti"],
            calculation_type="DTI",
            inputs={
                "accepted_monthly_income": Decimal("20000000.0000"),
                "total_monthly_debt_service": Decimal("22000000.0000"),
            },
            result_value=Decimal("1.10000000"),
            unit="RATIO",
        ),
        _calculation(
            calculation_id=calculation_ids["net-disposable-income"],
            calculation_type="NET_DISPOSABLE_INCOME",
            inputs={
                "accepted_monthly_income": Decimal("20000000.0000"),
                "total_monthly_debt_service": Decimal("22000000.0000"),
            },
            result_value=Decimal("-2000000.0000"),
            unit="VND",
        ),
        _calculation(
            calculation_id=calculation_ids["existing-monthly-obligations"],
            calculation_type="EXISTING_MONTHLY_OBLIGATIONS",
            inputs={"verified_existing_obligations": Decimal("9000000.0000")},
            result_value=Decimal("9000000.0000"),
            unit="VND",
        ),
    ]
    policy = _policy_context(
        analysis_case_id,
        status="FAIL",
        rule_code="CONSISTENT_VERIFIED_INCOME_REQUIRED",
        explanation=(
            "The synthetic policy requires consistent verified income evidence; the supplied "
            "synthetic documents contain unresolved differences."
        ),
    )
    shared = _shared_input_fields(
        analysis_case_id=analysis_case_id,
        customer_id=customer_id,
        loan_application_id=loan_application_id,
        authorized_source_ids=source_ids,
    )
    return MultiAgentAnalysisRequest(
        document_input=AgentInput(
            task_id=_run_uuid(analysis_case_id, "task:document"),
            **shared,
            context={
                "objective": objective,
                "assessment_date": "2026-07-18",
                "required_document_types": [
                    "IDENTITY_DOCUMENT",
                    "SALARY_SLIP",
                    "EMPLOYMENT_CONFIRMATION",
                    "ACCOUNT_STATEMENT",
                ],
                "required_document_indicators": {
                    "SALARY_SLIP": ["signature", "stamp"],
                    "EMPLOYMENT_CONFIRMATION": ["signature", "stamp"],
                },
                "documents": documents,
                "document_issues": [
                    "MISSING_PAGE: the synthetic account-statement page sequence is incomplete."
                ],
                "evidence": evidence,
            },
        ),
        credit_input=AgentInput(
            task_id=_run_uuid(analysis_case_id, "task:credit"),
            **shared,
            context={"objective": objective, "calculations": calculations},
        ),
        compliance_input=AgentInput(
            task_id=_run_uuid(analysis_case_id, "task:compliance"),
            **shared,
            context={"objective": objective, **policy["context"]},
        ),
        authorized_source_ids=source_ids,
        valid_calculation_ids=frozenset(calculation_ids.values()),
        valid_policy_clause_ids=frozenset({policy["clause_id"]}),
    )


def _shared_input_fields(
    *,
    analysis_case_id: UUID,
    customer_id: UUID,
    loan_application_id: UUID,
    authorized_source_ids: frozenset[UUID],
) -> dict[str, Any]:
    return {
        "analysis_case_id": analysis_case_id,
        "customer_id": customer_id,
        "loan_application_id": loan_application_id,
        "authorized_source_ids": authorized_source_ids,
    }


def _document_evidence(
    *,
    source_id: UUID,
    document_type: str,
    field_name: str,
    quoted_text: str,
) -> dict[str, Any]:
    return EvidenceReference(
        source_type="DOCUMENT_FIELD",
        source_id=source_id,
        source_locator={
            "resource": "mock.document.document_version",
            "document_version_id": str(source_id),
            "document_type": document_type,
            "page_number": 1,
            "field": field_name,
            "synthetic": True,
            "retrievable": False,
            "retrieval_mode": "INLINE_MOCK",
        },
        quoted_text=quoted_text,
        evidence_role=EvidenceRole.PRIMARY,
    ).model_dump(mode="python")


def _document(
    *,
    source_id: UUID,
    document_type: str,
    fields: dict[str, str],
    verification_status: str = "VERIFIED",
    presence_indicators: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "document_type": document_type,
        "verification_status": verification_status,
        "presence_indicators": presence_indicators or {},
        "extracted_fields": {
            field_name: {
                "normalized_value_text": value,
                "verification_status": (
                    "UNVERIFIED" if verification_status != "VERIFIED" else "VERIFIED"
                ),
                "source_id": source_id,
            }
            for field_name, value in fields.items()
        },
    }


def _calculation(
    *,
    calculation_id: UUID,
    calculation_type: str,
    inputs: dict[str, Decimal],
    result_value: Decimal,
    unit: str,
) -> dict[str, Any]:
    return {
        "calculation_id": calculation_id,
        "calculation_type": calculation_type,
        "calculation_version": "mock-deterministic-v1",
        "inputs": inputs,
        "result_value": result_value,
        "result_payload": {"synthetic": True},
        "unit": unit,
    }


def _policy_context(
    analysis_case_id: UUID,
    *,
    status: Literal["FAIL", "CONDITIONAL"],
    rule_code: str,
    explanation: str,
) -> dict[str, Any]:
    policy_id = _run_uuid(analysis_case_id, "policy:credit-assessment")
    policy_version_id = _run_uuid(analysis_case_id, "policy-version:2026-01")
    clause_id = _run_uuid(analysis_case_id, f"policy-clause:{rule_code.casefold()}")
    return {
        "clause_id": clause_id,
        "context": {
            "policy_references": [
                {
                    "policy_id": policy_id,
                    "policy_version_id": policy_version_id,
                    "clause_id": clause_id,
                    "clause_number": "SYNTHETIC-4.2",
                    "effective_date": "2026-01-01",
                }
            ],
            "policy_checks": [
                {
                    "status": status,
                    "rule_code": rule_code,
                    "clause_id": clause_id,
                    "actual_value": "SYNTHETIC_CASE_STATE",
                    "required_value": "AUTHORIZED_HUMAN_REVIEW",
                    "explanation": explanation,
                }
            ],
        },
    }


def _summary(code: MockScenarioCode) -> MockScenarioSummary:
    return next(item for item in _SCENARIOS if item.scenario_code is code)


def _scenario_code(value: MockScenarioCode | str) -> MockScenarioCode:
    if isinstance(value, MockScenarioCode):
        return value
    try:
        return MockScenarioCode(str(value).strip().upper())
    except ValueError as exc:
        supported = ", ".join(item.value for item in MockScenarioCode)
        raise ValueError(f"unsupported mock scenario; expected one of: {supported}") from exc


def _catalog_uuid(code: MockScenarioCode, name: str) -> UUID:
    return uuid5(_MOCK_NAMESPACE, f"catalog:{code.value}:{name}")


def _run_uuid(analysis_case_id: UUID, name: str) -> UUID:
    return uuid5(analysis_case_id, name)
