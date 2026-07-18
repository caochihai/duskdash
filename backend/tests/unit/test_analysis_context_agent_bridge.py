from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.agents.base import AgentInput
from app.agents.document_agent import DocumentAgent
from app.repositories.analysis_context_repository import build_document_context


@pytest.mark.asyncio
async def test_document_context_preserves_exact_field_evidence_for_agent_conflicts() -> None:
    case_id = uuid4()
    customer_id = uuid4()
    loan_id = uuid4()
    document_a = uuid4()
    document_b = uuid4()
    version_a = uuid4()
    version_b = uuid4()
    field_a = uuid4()
    field_b = uuid4()

    context = build_document_context(
        {
            "analysis_case_id": case_id,
            "customer_id": customer_id,
            "loan_application_id": loan_id,
            "assessment_date": date(2026, 7, 18),
        },
        [],
        [
            {
                "document_id": document_a,
                "document_type": "BUSINESS_LICENSE",
                "current_version_id": version_a,
                "verification_status": "VERIFIED",
                "processing_status": "COMPLETED",
                "scan_status": "CLEAN",
                "first_page_id": uuid4(),
            },
            {
                "document_id": document_b,
                "document_type": "TAX_REGISTRATION",
                "current_version_id": version_b,
                "verification_status": "VERIFIED",
                "processing_status": "COMPLETED",
                "scan_status": "CLEAN",
                "first_page_id": uuid4(),
            },
        ],
        [
            {
                "document_id": document_a,
                "document_type": "BUSINESS_LICENSE",
                "document_version_id": version_a,
                "field_id": field_a,
                "field_name": "tax_code",
                "normalized_value_text": "VN-001",
                "page_number": 1,
                "verification_status": "VERIFIED",
            },
            {
                "document_id": document_b,
                "document_type": "TAX_REGISTRATION",
                "document_version_id": version_b,
                "field_id": field_b,
                "field_name": "tax_code",
                "normalized_value_text": "VN-009",
                "page_number": 1,
                "verification_status": "UNVERIFIED",
            },
        ],
        [],
    )
    authorized = frozenset({field_a, field_b})

    output = await DocumentAgent().run(
        AgentInput(
            task_id=uuid4(),
            analysis_case_id=case_id,
            customer_id=customer_id,
            loan_application_id=loan_id,
            context=context,
            authorized_source_ids=authorized,
        )
    )

    conflict = next(
        finding
        for finding in output.findings
        if finding.finding_type == "CROSS_DOCUMENT_FIELD_CONFLICT"
    )
    assert {reference.source_id for reference in conflict.evidence} == {field_a, field_b}
    assert any(
        finding.finding_type == "UNVERIFIED_DOCUMENT_FIELD"
        for finding in output.findings
    )
