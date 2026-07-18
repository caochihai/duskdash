from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.agents.base import CalculationReference
from app.repositories.analysis_context_repository import (
    AnalysisContextRepository,
    build_authorized_source_ids,
    build_document_context,
    build_financial_context,
)


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self.rows)


class FakeSession:
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any]) -> FakeResult:
        self.calls.append((str(statement), params))
        return FakeResult(self.responses.pop(0))


def _uuid(suffix: int) -> UUID:
    return UUID(f"91000000-0000-4000-8000-{suffix:012d}")


def test_document_context_builds_completeness_presence_conflicts_and_evidence() -> None:
    case_id = _uuid(1)
    customer_id = _uuid(2)
    loan_id = _uuid(3)
    payslip_id = _uuid(10)
    identity_id = _uuid(11)
    payslip_version_id = _uuid(20)
    identity_version_id = _uuid(21)
    payslip_name_field_id = _uuid(30)
    identity_name_field_id = _uuid(31)
    seal_field_id = _uuid(32)
    signature_field_id = _uuid(33)

    context = build_document_context(
        {
            "analysis_case_id": case_id,
            "customer_id": customer_id,
            "loan_application_id": loan_id,
            "assessment_date": date(2026, 7, 18),
        },
        [
            {
                "id": _uuid(40),
                "requirement_code": "PAYSLIP-LATEST",
                "document_type": "PAYSLIP",
                "requirement_status": "VALID",
                "mandatory_level": "MANDATORY",
                "source_policy_clause_id": _uuid(41),
                "linked_document_id": payslip_id,
            },
            {
                "id": _uuid(42),
                "requirement_code": "BANK-STATEMENT-12M",
                "document_type": "BANK_STATEMENT",
                "requirement_status": "REQUIRED",
                "mandatory_level": "MANDATORY",
                "source_policy_clause_id": _uuid(41),
                "linked_document_id": None,
            },
            {
                "id": _uuid(43),
                "requirement_code": "OPTIONAL-REFERENCE",
                "document_type": "REFERENCE_LETTER",
                "requirement_status": "REQUIRED",
                "mandatory_level": "OPTIONAL",
                "source_policy_clause_id": None,
                "linked_document_id": None,
            },
        ],
        [
            {
                "document_id": payslip_id,
                "document_type": "PAYSLIP",
                "document_subtype": None,
                "document_date": date(2026, 6, 30),
                "valid_until": date(2026, 12, 31),
                "verification_status": "VERIFIED",
                "processing_status": "COMPLETED",
                "current_version_id": payslip_version_id,
                "scan_status": "CLEAN",
                "first_page_id": _uuid(50),
            },
            {
                "document_id": identity_id,
                "document_type": "IDENTITY_DOCUMENT",
                "document_subtype": None,
                "document_date": date(2020, 1, 1),
                "valid_until": date(2025, 12, 31),
                "verification_status": "UNVERIFIED",
                "processing_status": "COMPLETED",
                "current_version_id": identity_version_id,
                "scan_status": "CLEAN",
                "first_page_id": _uuid(51),
            },
        ],
        [
            {
                "document_id": payslip_id,
                "document_type": "PAYSLIP",
                "document_version_id": payslip_version_id,
                "field_id": payslip_name_field_id,
                "field_name": "customer_name",
                "normalized_value_text": "NGUYEN VAN A",
                "corrected_value_text": None,
                "ocr_value_text": "Nguyen Van A",
                "value_number": None,
                "value_date": None,
                "page_number": 1,
                "verification_status": "VERIFIED",
            },
            {
                "document_id": payslip_id,
                "document_type": "PAYSLIP",
                "document_version_id": payslip_version_id,
                "field_id": seal_field_id,
                "field_name": "red_seal_present",
                "normalized_value_text": "false",
                "corrected_value_text": None,
                "ocr_value_text": "false",
                "value_number": None,
                "value_date": None,
                "page_number": 1,
                "verification_status": "VERIFIED",
            },
            {
                "document_id": identity_id,
                "document_type": "IDENTITY_DOCUMENT",
                "document_version_id": identity_version_id,
                "field_id": identity_name_field_id,
                "field_name": "customer_name",
                "normalized_value_text": "NGUYEN VAN B",
                "corrected_value_text": None,
                "ocr_value_text": "Nguyen Van B",
                "value_number": None,
                "value_date": None,
                "page_number": 1,
                "verification_status": "VERIFIED",
            },
            {
                "document_id": identity_id,
                "document_type": "IDENTITY_DOCUMENT",
                "document_version_id": identity_version_id,
                "field_id": signature_field_id,
                "field_name": "signature_detected",
                "normalized_value_text": "yes",
                "corrected_value_text": None,
                "ocr_value_text": "yes",
                "value_number": None,
                "value_date": None,
                "page_number": 1,
                "verification_status": "UNVERIFIED",
            },
        ],
        [
            {
                "document_id": payslip_id,
                "document_type": "PAYSLIP",
                "document_version_id": payslip_version_id,
                "issue_id": _uuid(60),
                "issue_type": "LOW_OCR_CONFIDENCE",
                "severity": "MEDIUM",
                "title": "Income field needs review",
                "description": "The extracted value is below the configured confidence.",
                "field_id": payslip_name_field_id,
                "status": "OPEN",
                "detected_by": "RULE",
            },
            {
                "document_id": identity_id,
                "document_type": "IDENTITY_DOCUMENT",
                "document_version_id": identity_version_id,
                "issue_id": _uuid(61),
                "issue_type": "REVIEWED_NOTE",
                "severity": "LOW",
                "title": "Already resolved",
                "description": "No remaining action.",
                "field_id": None,
                "status": "RESOLVED",
                "detected_by": "HUMAN",
            },
        ],
    )

    assert context["required_document_types"] == ["BANK_STATEMENT", "PAYSLIP"]
    assert context["available_document_types"] == ["IDENTITY_DOCUMENT", "PAYSLIP"]
    documents = {item["document_type"]: item for item in context["documents"]}
    assert documents["PAYSLIP"]["presence_indicators"] == {"seal": False}
    assert documents["PAYSLIP"]["required_indicators"] == ["seal"]
    assert documents["PAYSLIP"]["extracted_fields"]["customer_name"] == {
        "normalized_value_text": "NGUYEN VAN A",
        "verification_status": "VERIFIED",
        "source_id": payslip_name_field_id,
    }
    assert documents["IDENTITY_DOCUMENT"]["presence_indicators"] == {"signature": True}
    assert documents["IDENTITY_DOCUMENT"]["is_expired"] is True
    assert len(context["document_issues"]) == 1
    assert "Income field needs review" in context["document_issues"][0]
    assert len(context["cross_document_conflicts"]) == 1
    conflict = context["cross_document_conflicts"][0]
    assert conflict["field_name"] == "customer_name"
    assert {item["evidence"]["source_id"] for item in conflict["values"]} == {
        payslip_name_field_id,
        identity_name_field_id,
    }
    assert all(
        item["evidence"]["evidence_role"] == "CONTRADICTING"
        for item in conflict["values"]
    )
    assert "do not establish legal authenticity" in context["authenticity_notice"]


def test_financial_context_uses_decimal_calculation_refs_and_currency_safe_debt_totals() -> None:
    calculation_id = _uuid(70)
    scope = {
        "analysis_case_id": _uuid(1),
        "customer_id": _uuid(2),
        "loan_application_id": _uuid(3),
        "application_number": "LA-2026-001",
        "requested_amount": Decimal("700000000.0000"),
        "currency": "VND",
        "requested_term_months": 60,
        "loan_purpose": "HOME_PURCHASE",
        "interest_rate_assumption": Decimal("0.10000000"),
        "repayment_method": "ANNUITY",
        "loan_status": "UNDER_ANALYSIS",
    }
    context = build_financial_context(
        scope,
        [
            {
                "id": calculation_id,
                "calculation_type": "AFFORDABILITY",
                "calculation_version": "1.0",
                "inputs_json": '{"existing_obligations":15000000.0000}',
                "formula": "persisted deterministic formula",
                "result_value": Decimal("1.2000000000"),
                "result_payload_json": (
                    '{"dti":1.20,"dscr":0.83,'
                    '"net_disposable_income":-2000000.0000,'
                    '"projected_monthly_payment":17000000.0000}'
                ),
                "unit": "RATIO",
            }
        ],
        [
            {
                "id": _uuid(71),
                "calculation_version": "1.0",
                "monthly_declared_income": Decimal("30000000.0000"),
                "monthly_verified_income": Decimal("22000000.0000"),
                "monthly_accepted_income": Decimal("25000000.0000"),
                "monthly_existing_obligations": Decimal("15000000.0000"),
                "projected_monthly_payment": Decimal("17000000.0000"),
                "dti": Decimal("1.28000000"),
                "dscr": Decimal("0.78125000"),
                "ltv": Decimal("0.70000000"),
                "net_disposable_income": Decimal("-7000000.0000"),
                "stress_interest_rate": Decimal("0.13000000"),
                "stress_dti": Decimal("1.40000000"),
                "result": "FAIL",
                "calculation_payload_json": "{}",
            }
        ],
        [
            {
                "id": _uuid(80),
                "party_id": _uuid(90),
                "lender_name": "Bank A",
                "obligation_type": "MORTGAGE",
                "outstanding_balance": Decimal("300000000.0000"),
                "monthly_payment": Decimal("10000000.0000"),
                "credit_limit": None,
                "currency": "VND",
                "verified_status": "VERIFIED",
                "source_type": "DOCUMENT_FIELD",
                "source_id": _uuid(30),
                "as_of_date": date(2026, 6, 30),
            },
            {
                "id": _uuid(81),
                "party_id": _uuid(90),
                "lender_name": "Bank B",
                "obligation_type": "CREDIT_CARD",
                "outstanding_balance": Decimal("50000000.0000"),
                "monthly_payment": Decimal("5000000.0000"),
                "credit_limit": Decimal("100000000.0000"),
                "currency": "VND",
                "verified_status": "UNVERIFIED",
                "source_type": "CUSTOMER_RECORD",
                "source_id": _uuid(2),
                "as_of_date": date(2026, 7, 1),
            },
        ],
    )

    calculation = context["calculations"][0]
    assert CalculationReference.model_validate(calculation).calculation_id == calculation_id
    assert calculation["calculation_id"] == calculation_id
    assert calculation["inputs"]["existing_obligations"] == Decimal("15000000.0000")
    assert calculation["result_payload"]["dti"] == Decimal("1.20")
    assert context["repayment_metrics"]["DTI"] == Decimal("1.20")
    assert context["repayment_metrics"]["DSCR"] == Decimal("0.83")
    assert context["repayment_metrics"]["NET_DISPOSABLE_INCOME"] == Decimal(
        "-2000000.0000"
    )
    debt_summary = context["debt_summary"]
    assert debt_summary["verified_obligation_count"] == 1
    assert debt_summary["unverified_obligation_count"] == 1
    assert debt_summary["by_currency"] == [
        {
            "currency": "VND",
            "obligation_count": 2,
            "outstanding_balance": Decimal("350000000.0000"),
            "monthly_payment": Decimal("15000000.0000"),
            "credit_limit": Decimal("100000000.0000"),
        }
    ]
    assert "do not approve or reject" in context["decision_notice"]


@pytest.mark.asyncio
async def test_repository_queries_are_anchored_at_rls_analysis_case() -> None:
    case_id = _uuid(1)
    scope = {
        "analysis_case_id": case_id,
        "customer_id": _uuid(2),
        "loan_application_id": _uuid(3),
        "assessment_date": date(2026, 7, 18),
    }
    session = FakeSession([[scope], [], [], [], []])
    repository = AnalysisContextRepository(session)  # type: ignore[arg-type]

    context = await repository.load_document_context(case_id)

    assert context["analysis_case_id"] == case_id
    assert len(session.calls) == 5
    assert all("ai.analysis_case" in sql for sql, _ in session.calls)
    assert all(params == {"case_id": case_id} for _, params in session.calls)


@pytest.mark.asyncio
async def test_repository_rejects_missing_or_unauthorized_case_before_context_queries() -> None:
    session = FakeSession([[]])
    repository = AnalysisContextRepository(session)  # type: ignore[arg-type]

    with pytest.raises(LookupError, match="outside the authorized scope"):
        await repository.load_financial_context(_uuid(1))

    assert len(session.calls) == 1
    assert "FROM ai.analysis_case AS ac" in session.calls[0][0]


@pytest.mark.asyncio
async def test_authorized_sources_are_case_scoped_and_deduplicated() -> None:
    case_id = _uuid(1)
    source_ids = [_uuid(2), _uuid(3), _uuid(2)]
    session = FakeSession([[{"source_id": item} for item in source_ids]])
    repository = AnalysisContextRepository(session)  # type: ignore[arg-type]

    result = await repository.authorized_source_ids(case_id)

    assert result == frozenset({_uuid(2), _uuid(3)})
    assert "FROM ai.analysis_case AS ac" in session.calls[0][0]
    assert build_authorized_source_ids([{"source_id": None}]) == frozenset()


def test_financial_builder_rejects_binary_float_json() -> None:
    with pytest.raises(TypeError, match="binary float"):
        build_financial_context(
            {
                "analysis_case_id": _uuid(1),
                "customer_id": _uuid(2),
                "loan_application_id": _uuid(3),
            },
            [
                {
                    "id": _uuid(70),
                    "calculation_type": "DTI",
                    "calculation_version": "1.0",
                    "inputs": {"income": 1.5},
                    "result_payload": {},
                    "result_value": Decimal("0.5"),
                }
            ],
            [],
            [],
        )
