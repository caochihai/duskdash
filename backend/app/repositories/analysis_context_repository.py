"""RLS-scoped read adapter for expert-agent document and financial context."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import Record, fetch_all, fetch_one

_CLOSED_ISSUE_STATUSES = frozenset({"CLOSED", "DISMISSED", "RESOLVED"})
_NON_REQUIRED_CHECKLIST_STATUSES = frozenset({"NOT_APPLICABLE", "WAIVED"})
_PRESENCE_INDICATORS = ("signature", "seal", "stamp")
_TRUE_SIGNALS = frozenset(
    {
        "1",
        "co",
        "có",
        "detected",
        "exists",
        "found",
        "present",
        "true",
        "yes",
    }
)
_FALSE_SIGNALS = frozenset(
    {
        "0",
        "absent",
        "false",
        "khong",
        "không",
        "missing",
        "no",
        "not detected",
        "not found",
        "not present",
    }
)

_DOCUMENT_SCOPE_SQL = """
SELECT ac.id AS analysis_case_id,
       ac.customer_id,
       ac.loan_application_id,
       CURRENT_DATE AS assessment_date
FROM ai.analysis_case AS ac
WHERE ac.id = :case_id
"""

_CHECKLIST_SQL = """
SELECT lci.id,
       lci.requirement_code,
       lci.document_type,
       lci.requirement_status,
       lci.mandatory_level,
       lci.source_policy_clause_id,
       lci.linked_document_id
FROM ai.analysis_case AS ac
JOIN credit.loan_checklist_item AS lci
  ON lci.loan_application_id = ac.loan_application_id
WHERE ac.id = :case_id
ORDER BY lci.requirement_code, lci.id
"""

_DOCUMENTS_SQL = """
SELECT DISTINCT ON (d.id)
       d.id AS document_id,
       d.document_type,
       d.document_subtype,
       d.document_date,
       d.valid_from,
       d.valid_until,
       d.verification_status,
       d.processing_status,
       dv.id AS current_version_id,
       dv.version_number,
       dv.scan_status,
       first_page.id AS first_page_id
FROM ai.analysis_case AS ac
JOIN document.document AS d
  ON (
      EXISTS (
          SELECT 1
          FROM document.document_link AS dl
          WHERE dl.document_id = d.id
            AND (
                (dl.entity_type = 'CUSTOMER' AND dl.entity_id = ac.customer_id)
                OR (
                    dl.entity_type = 'LOAN_APPLICATION'
                    AND dl.entity_id = ac.loan_application_id
                )
            )
      )
      OR EXISTS (
          SELECT 1
          FROM credit.loan_checklist_item AS lci
          WHERE lci.loan_application_id = ac.loan_application_id
            AND lci.linked_document_id = d.id
      )
  )
JOIN document.document_version AS dv
  ON dv.document_id = d.id
 AND dv.is_current
LEFT JOIN LATERAL (
    SELECT dp.id
    FROM document.document_page AS dp
    WHERE dp.document_version_id = dv.id
    ORDER BY dp.page_number, dp.id
    LIMIT 1
) AS first_page ON TRUE
WHERE ac.id = :case_id
ORDER BY d.id, dv.version_number DESC, dv.id
"""

_FIELDS_SQL = """
SELECT d.id AS document_id,
       d.document_type,
       dv.id AS document_version_id,
       ef.id AS field_id,
       ef.field_name,
       ef.value_type,
       ef.ocr_value_text,
       ef.normalized_value_text,
       ef.corrected_value_text,
       ef.value_number,
       ef.value_date,
       ef.page_number,
       ef.confidence,
       ef.verification_status,
       ef.verified_at
FROM ai.analysis_case AS ac
JOIN document.document AS d
  ON (
      EXISTS (
          SELECT 1
          FROM document.document_link AS dl
          WHERE dl.document_id = d.id
            AND (
                (dl.entity_type = 'CUSTOMER' AND dl.entity_id = ac.customer_id)
                OR (
                    dl.entity_type = 'LOAN_APPLICATION'
                    AND dl.entity_id = ac.loan_application_id
                )
            )
      )
      OR EXISTS (
          SELECT 1
          FROM credit.loan_checklist_item AS lci
          WHERE lci.loan_application_id = ac.loan_application_id
            AND lci.linked_document_id = d.id
      )
  )
JOIN document.document_version AS dv
  ON dv.document_id = d.id
 AND dv.is_current
JOIN document.extracted_field AS ef
  ON ef.document_version_id = dv.id
WHERE ac.id = :case_id
ORDER BY d.id,
         ef.field_name,
         (ef.corrected_value_text IS NOT NULL) DESC,
         (ef.verification_status = 'VERIFIED') DESC,
         ef.verified_at DESC NULLS LAST,
         ef.confidence DESC NULLS LAST,
         ef.id
"""

_ISSUES_SQL = """
SELECT d.id AS document_id,
       d.document_type,
       dv.id AS document_version_id,
       di.id AS issue_id,
       di.issue_type,
       di.severity,
       di.title,
       di.description,
       di.field_id,
       di.status,
       di.detected_by,
       di.created_at
FROM ai.analysis_case AS ac
JOIN document.document AS d
  ON (
      EXISTS (
          SELECT 1
          FROM document.document_link AS dl
          WHERE dl.document_id = d.id
            AND (
                (dl.entity_type = 'CUSTOMER' AND dl.entity_id = ac.customer_id)
                OR (
                    dl.entity_type = 'LOAN_APPLICATION'
                    AND dl.entity_id = ac.loan_application_id
                )
            )
      )
      OR EXISTS (
          SELECT 1
          FROM credit.loan_checklist_item AS lci
          WHERE lci.loan_application_id = ac.loan_application_id
            AND lci.linked_document_id = d.id
      )
  )
JOIN document.document_version AS dv
  ON dv.document_id = d.id
 AND dv.is_current
JOIN document.document_issue AS di
  ON di.document_version_id = dv.id
WHERE ac.id = :case_id
ORDER BY d.id, di.created_at, di.id
"""

_FINANCIAL_SCOPE_SQL = """
SELECT ac.id AS analysis_case_id,
       ac.customer_id,
       ac.loan_application_id,
       la.application_number,
       la.requested_amount,
       la.currency,
       la.requested_term_months,
       la.loan_purpose,
       la.interest_rate_assumption,
       la.repayment_method,
       la.status AS loan_status
FROM ai.analysis_case AS ac
LEFT JOIN credit.loan_application AS la
  ON la.id = ac.loan_application_id
WHERE ac.id = :case_id
"""

_CALCULATIONS_SQL = """
SELECT DISTINCT ON (UPPER(cr.calculation_type))
       cr.id,
       cr.loan_application_id,
       cr.analysis_case_id,
       cr.calculation_type,
       cr.calculation_version,
       cr.inputs::text AS inputs_json,
       cr.formula,
       cr.result_value,
       cr.result_payload::text AS result_payload_json,
       cr.unit,
       cr.calculated_at,
       cr.created_by_type,
       cr.created_by_id
FROM ai.analysis_case AS ac
JOIN credit.calculation_record AS cr
  ON cr.loan_application_id = ac.loan_application_id
 AND (cr.analysis_case_id = ac.id OR cr.analysis_case_id IS NULL)
WHERE ac.id = :case_id
ORDER BY UPPER(cr.calculation_type),
         (cr.analysis_case_id = ac.id) DESC,
         cr.calculated_at DESC,
         cr.id DESC
"""

_AFFORDABILITY_SQL = """
SELECT aa.id,
       aa.loan_application_id,
       aa.calculation_version,
       aa.monthly_declared_income,
       aa.monthly_verified_income,
       aa.monthly_accepted_income,
       aa.monthly_existing_obligations,
       aa.projected_monthly_payment,
       aa.dti,
       aa.dscr,
       aa.ltv,
       aa.net_disposable_income,
       aa.stress_interest_rate,
       aa.stress_dti,
       aa.result,
       aa.calculation_payload::text AS calculation_payload_json,
       aa.calculated_at
FROM ai.analysis_case AS ac
JOIN credit.affordability_assessment AS aa
  ON aa.loan_application_id = ac.loan_application_id
WHERE ac.id = :case_id
ORDER BY aa.calculated_at DESC, aa.id DESC
LIMIT 1
"""

_OBLIGATIONS_SQL = """
SELECT eo.id,
       eo.party_id,
       eo.lender_name,
       eo.obligation_type,
       eo.outstanding_balance,
       eo.monthly_payment,
       eo.credit_limit,
       eo.currency,
       eo.verified_status,
       eo.source_type,
       eo.source_id,
       eo.as_of_date
FROM ai.analysis_case AS ac
JOIN credit.existing_obligation AS eo
  ON eo.loan_application_id = ac.loan_application_id
WHERE ac.id = :case_id
ORDER BY eo.as_of_date DESC, eo.id
"""

_AUTHORIZED_SOURCES_SQL = """
WITH scoped_case AS (
    SELECT ac.id, ac.customer_id, ac.loan_application_id
    FROM ai.analysis_case AS ac
    WHERE ac.id = :case_id
),
scoped_documents AS (
    SELECT DISTINCT dl.document_id
    FROM scoped_case AS ac
    JOIN document.document_link AS dl
      ON (dl.entity_type = 'CUSTOMER' AND dl.entity_id = ac.customer_id)
      OR (
          dl.entity_type = 'LOAN_APPLICATION'
          AND dl.entity_id = ac.loan_application_id
      )
    UNION
    SELECT DISTINCT lci.linked_document_id AS document_id
    FROM scoped_case AS ac
    JOIN credit.loan_checklist_item AS lci
      ON lci.loan_application_id = ac.loan_application_id
    WHERE lci.linked_document_id IS NOT NULL
),
current_versions AS (
    SELECT dv.id, dv.document_id
    FROM scoped_documents AS sd
    JOIN document.document AS d ON d.id = sd.document_id
    JOIN document.document_version AS dv
      ON dv.document_id = d.id
     AND dv.is_current
)
SELECT ac.customer_id AS source_id FROM scoped_case AS ac
UNION
SELECT ac.loan_application_id AS source_id
FROM scoped_case AS ac
WHERE ac.loan_application_id IS NOT NULL
UNION
SELECT ef.id AS source_id
FROM current_versions AS cv
JOIN document.extracted_field AS ef ON ef.document_version_id = cv.id
UNION
SELECT dp.id AS source_id
FROM current_versions AS cv
JOIN document.document_page AS dp ON dp.document_version_id = cv.id
UNION
SELECT dc.id AS source_id
FROM current_versions AS cv
JOIN document.document_chunk AS dc ON dc.document_version_id = cv.id
UNION
SELECT cr.id AS source_id
FROM scoped_case AS ac
JOIN credit.calculation_record AS cr
  ON cr.loan_application_id = ac.loan_application_id
 AND (cr.analysis_case_id = ac.id OR cr.analysis_case_id IS NULL)
UNION
SELECT pc.clause_id AS source_id
FROM scoped_case AS ac
JOIN credit.policy_check AS pc
  ON pc.loan_application_id = ac.loan_application_id
 AND (pc.analysis_case_id = ac.id OR pc.analysis_case_id IS NULL)
WHERE pc.clause_id IS NOT NULL
UNION
SELECT eo.source_id
FROM scoped_case AS ac
JOIN credit.existing_obligation AS eo
  ON eo.loan_application_id = ac.loan_application_id
WHERE eo.source_id IS NOT NULL
"""


class AnalysisContextRepository:
    """Load narrowly scoped records for deterministic expert-agent inputs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_document_context(self, analysis_case_id: UUID) -> Record:
        params = {"case_id": analysis_case_id}
        scope = await fetch_one(self.session, _DOCUMENT_SCOPE_SQL, params)
        if scope is None:
            raise LookupError("Analysis case is missing or outside the authorized scope")
        checklist = await fetch_all(self.session, _CHECKLIST_SQL, params)
        documents = await fetch_all(self.session, _DOCUMENTS_SQL, params)
        fields = await fetch_all(self.session, _FIELDS_SQL, params)
        issues = await fetch_all(self.session, _ISSUES_SQL, params)
        return build_document_context(scope, checklist, documents, fields, issues)

    async def load_financial_context(self, analysis_case_id: UUID) -> Record:
        params = {"case_id": analysis_case_id}
        scope = await fetch_one(self.session, _FINANCIAL_SCOPE_SQL, params)
        if scope is None:
            raise LookupError("Analysis case is missing or outside the authorized scope")
        calculations = await fetch_all(self.session, _CALCULATIONS_SQL, params)
        affordability = await fetch_all(self.session, _AFFORDABILITY_SQL, params)
        obligations = await fetch_all(self.session, _OBLIGATIONS_SQL, params)
        return build_financial_context(scope, calculations, affordability, obligations)

    async def authorized_source_ids(self, analysis_case_id: UUID) -> frozenset[UUID]:
        rows = await fetch_all(
            self.session,
            _AUTHORIZED_SOURCES_SQL,
            {"case_id": analysis_case_id},
        )
        return build_authorized_source_ids(rows)


def build_document_context(
    scope: Mapping[str, Any],
    checklist_rows: Sequence[Mapping[str, Any]],
    document_rows: Sequence[Mapping[str, Any]],
    field_rows: Sequence[Mapping[str, Any]],
    issue_rows: Sequence[Mapping[str, Any]],
) -> Record:
    """Build agent context from already-authorized flat database rows."""

    assessment_date = _date_value(scope.get("assessment_date"))
    fields_by_document: defaultdict[UUID, list[Mapping[str, Any]]] = defaultdict(list)
    for row in field_rows:
        fields_by_document[_uuid_value(row.get("document_id"), "document_id")].append(row)

    evidence_by_key: dict[tuple[str, UUID], Record] = {}
    documents: list[Record] = []
    for row in document_rows:
        document_id = _uuid_value(row.get("document_id"), "document_id")
        current_version_id = _uuid_value(row.get("current_version_id"), "current_version_id")
        rows = sorted(fields_by_document.get(document_id, ()), key=_field_sort_key)
        extracted_fields: dict[str, Any] = {}
        presence_indicators: dict[str, bool | None] = {}
        required_indicators: set[str] = set()
        for field in rows:
            field_name = _normalized_field_name(field.get("field_name"))
            value = _effective_field_value(field)
            indicator = _presence_indicator(field_name)
            if indicator is not None:
                required_indicators.add(indicator)
                presence_indicators.setdefault(indicator, _presence_value(value))
            elif value is not None:
                extracted_fields.setdefault(
                    field_name,
                    {
                        "normalized_value_text": value,
                        "verification_status": str(
                            field.get("verification_status") or "UNVERIFIED"
                        ).upper(),
                        "source_id": _uuid_value(field.get("field_id"), "field_id"),
                    },
                )

            field_id = _uuid_value(field.get("field_id"), "field_id")
            evidence = _field_evidence(field, document_id, current_version_id)
            evidence_by_key.setdefault(("DOCUMENT_FIELD", field_id), evidence)

        first_field = rows[0] if rows else None
        first_page_id = _optional_uuid(row.get("first_page_id"))
        if first_field is not None:
            source_id = _uuid_value(first_field.get("field_id"), "field_id")
            source_type = "DOCUMENT_FIELD"
            source_locator = dict(
                evidence_by_key[("DOCUMENT_FIELD", source_id)]["source_locator"]
            )
        elif first_page_id is not None:
            source_id = first_page_id
            source_type = "DOCUMENT_PAGE"
            source_locator = {
                "document_id": str(document_id),
                "document_version_id": str(current_version_id),
                "page_number": 1,
            }
        else:
            # ai.evidence_link has no DOCUMENT_VERSION source type. Until a page
            # or field exists, anchor the metadata observation to the scoped loan
            # (or customer-only case) and keep the exact document IDs in locator.
            loan_application_id = _optional_uuid(scope.get("loan_application_id"))
            if loan_application_id is not None:
                source_id = loan_application_id
                source_type = "LOAN_RECORD"
            else:
                source_id = _uuid_value(scope.get("customer_id"), "customer_id")
                source_type = "CUSTOMER_RECORD"
            source_locator = {
                "document_id": str(document_id),
                "document_version_id": str(current_version_id),
            }
        evidence_by_key.setdefault(
            (source_type, source_id),
            {
                "source_type": source_type,
                "source_id": source_id,
                "source_locator": source_locator,
                "evidence_role": "SUPPORTING",
            },
        )

        expiry_date = _date_value(row.get("valid_until"))
        documents.append(
            {
                "document_id": document_id,
                "current_version_id": current_version_id,
                "source_id": source_id,
                "document_type": _normalized_document_type(row.get("document_type")),
                "document_subtype": row.get("document_subtype"),
                "document_date": _date_value(row.get("document_date")),
                "verification_status": str(
                    row.get("verification_status") or "UNVERIFIED"
                ).upper(),
                "processing_status": str(row.get("processing_status") or "UNKNOWN").upper(),
                "scan_status": str(row.get("scan_status") or "UNKNOWN").upper(),
                "expiry_date": expiry_date,
                "is_expired": bool(
                    expiry_date is not None
                    and assessment_date is not None
                    and expiry_date < assessment_date
                ),
                "presence_indicators": presence_indicators,
                "required_indicators": sorted(required_indicators),
                "extracted_fields": extracted_fields,
            }
        )

    structured_issues = [_issue_record(row) for row in issue_rows]
    active_issues = [
        issue
        for issue in structured_issues
        if str(issue["status"]).upper() not in _CLOSED_ISSUE_STATUSES
    ]
    conflicts = _cross_document_conflicts(document_rows, field_rows)
    for conflict in conflicts:
        for value in conflict["values"]:
            evidence = value["evidence"]
            evidence_by_key.setdefault(
                (str(evidence["source_type"]), evidence["source_id"]),
                evidence,
            )

    checklist = [_checklist_record(row) for row in checklist_rows]
    required_document_types = sorted(
        {
            item["document_type"]
            for item in checklist
            if item["document_type"]
            and str(item["mandatory_level"]).upper() != "OPTIONAL"
            and str(item["requirement_status"]).upper()
            not in _NON_REQUIRED_CHECKLIST_STATUSES
        }
    )
    available_document_types = sorted(
        {str(item["document_type"]) for item in documents if item["document_type"]}
    )
    indicator_requirements = {
        str(item["document_type"]): list(item["required_indicators"])
        for item in documents
        if item["required_indicators"]
    }

    return {
        "analysis_case_id": _uuid_value(scope.get("analysis_case_id"), "analysis_case_id"),
        "customer_id": _uuid_value(scope.get("customer_id"), "customer_id"),
        "loan_application_id": _optional_uuid(scope.get("loan_application_id")),
        "assessment_date": assessment_date,
        "required_document_types": required_document_types,
        "available_document_types": available_document_types,
        "required_document_indicators": indicator_requirements,
        "checklist": checklist,
        "documents": documents,
        "issues": structured_issues,
        "document_issues": [
            f"{issue['severity']} {issue['title']}: {issue['description']}"
            for issue in active_issues
        ],
        "cross_document_conflicts": conflicts,
        "evidence": list(evidence_by_key.values()),
        "authenticity_notice": (
            "Signature, seal, and stamp values are recorded presence signals only; "
            "they do not establish legal authenticity."
        ),
    }


def build_financial_context(
    scope: Mapping[str, Any],
    calculation_rows: Sequence[Mapping[str, Any]],
    affordability_rows: Sequence[Mapping[str, Any]],
    obligation_rows: Sequence[Mapping[str, Any]],
) -> Record:
    """Build Decimal-safe repayment context without applying policy thresholds."""

    calculations = [_calculation_reference(row) for row in calculation_rows]
    affordability = (
        _affordability_record(affordability_rows[0]) if affordability_rows else None
    )
    obligations = [_obligation_record(row) for row in obligation_rows]
    repayment_metrics = _repayment_metrics(calculations, affordability)

    debt_by_currency: dict[str, Record] = {}
    for obligation in obligations:
        currency = str(obligation["currency"])
        totals = debt_by_currency.setdefault(
            currency,
            {
                "currency": currency,
                "obligation_count": 0,
                "outstanding_balance": Decimal("0"),
                "monthly_payment": Decimal("0"),
                "credit_limit": Decimal("0"),
            },
        )
        totals["obligation_count"] += 1
        for field in ("outstanding_balance", "monthly_payment", "credit_limit"):
            totals[field] += obligation[field] or Decimal("0")

    verified_count = sum(
        str(item["verified_status"]).upper() in {"CONFIRMED", "VALID", "VERIFIED"}
        for item in obligations
    )
    return {
        "analysis_case_id": _uuid_value(scope.get("analysis_case_id"), "analysis_case_id"),
        "customer_id": _uuid_value(scope.get("customer_id"), "customer_id"),
        "loan_application_id": _optional_uuid(scope.get("loan_application_id")),
        "loan_request": {
            "application_number": scope.get("application_number"),
            "requested_amount": _decimal_value(scope.get("requested_amount")),
            "currency": scope.get("currency"),
            "requested_term_months": scope.get("requested_term_months"),
            "loan_purpose": scope.get("loan_purpose"),
            "interest_rate_assumption": _decimal_value(
                scope.get("interest_rate_assumption")
            ),
            "repayment_method": scope.get("repayment_method"),
            "status": scope.get("loan_status"),
        },
        "calculations": calculations,
        "calculation_metadata": [
            {
                "calculation_id": _uuid_value(row.get("id"), "calculation id"),
                "formula": row.get("formula"),
                "calculated_at": row.get("calculated_at"),
                "created_by_type": row.get("created_by_type"),
                "created_by_id": _optional_uuid(row.get("created_by_id")),
            }
            for row in calculation_rows
        ],
        "calculation_ids": [item["calculation_id"] for item in calculations],
        "affordability_assessment": affordability,
        "repayment_metrics": repayment_metrics,
        "existing_obligations": obligations,
        "debt_summary": {
            "obligation_count": len(obligations),
            "verified_obligation_count": verified_count,
            "unverified_obligation_count": len(obligations) - verified_count,
            "by_currency": [debt_by_currency[key] for key in sorted(debt_by_currency)],
        },
        "decision_notice": (
            "These persisted calculations support human review and do not approve or reject a loan."
        ),
    }


def build_authorized_source_ids(rows: Sequence[Mapping[str, Any]]) -> frozenset[UUID]:
    """Return de-duplicated UUIDs from the RLS/case-scoped source query."""

    return frozenset(
        source_id
        for row in rows
        if (source_id := _optional_uuid(row.get("source_id"))) is not None
    )


def _checklist_record(row: Mapping[str, Any]) -> Record:
    return {
        "checklist_item_id": _uuid_value(row.get("id"), "checklist item id"),
        "requirement_code": str(row.get("requirement_code") or ""),
        "document_type": (
            _normalized_document_type(row.get("document_type"))
            if row.get("document_type")
            else None
        ),
        "requirement_status": str(row.get("requirement_status") or "UNKNOWN").upper(),
        "mandatory_level": str(row.get("mandatory_level") or "UNKNOWN").upper(),
        "source_policy_clause_id": _optional_uuid(row.get("source_policy_clause_id")),
        "linked_document_id": _optional_uuid(row.get("linked_document_id")),
    }


def _issue_record(row: Mapping[str, Any]) -> Record:
    return {
        "issue_id": _uuid_value(row.get("issue_id"), "issue_id"),
        "document_id": _uuid_value(row.get("document_id"), "document_id"),
        "document_version_id": _uuid_value(
            row.get("document_version_id"), "document_version_id"
        ),
        "document_type": _normalized_document_type(row.get("document_type")),
        "issue_type": str(row.get("issue_type") or "UNKNOWN").upper(),
        "severity": str(row.get("severity") or "UNKNOWN").upper(),
        "title": str(row.get("title") or "Document issue"),
        "description": str(row.get("description") or ""),
        "field_id": _optional_uuid(row.get("field_id")),
        "status": str(row.get("status") or "OPEN").upper(),
        "detected_by": str(row.get("detected_by") or "UNKNOWN").upper(),
    }


def _calculation_reference(row: Mapping[str, Any]) -> Record:
    return {
        "calculation_id": _uuid_value(row.get("id"), "calculation id"),
        "calculation_type": str(row.get("calculation_type") or "").upper(),
        "calculation_version": row.get("calculation_version"),
        "inputs": _json_object(row.get("inputs_json", row.get("inputs", {}))),
        "result_value": _decimal_value(row.get("result_value")),
        "result_payload": _json_object(
            row.get("result_payload_json", row.get("result_payload", {}))
        ),
        "unit": row.get("unit"),
    }


def _affordability_record(row: Mapping[str, Any]) -> Record:
    numeric_fields = (
        "monthly_declared_income",
        "monthly_verified_income",
        "monthly_accepted_income",
        "monthly_existing_obligations",
        "projected_monthly_payment",
        "dti",
        "dscr",
        "ltv",
        "net_disposable_income",
        "stress_interest_rate",
        "stress_dti",
    )
    result: Record = {
        "assessment_id": _uuid_value(row.get("id"), "affordability assessment id"),
        "calculation_version": row.get("calculation_version"),
        "result": row.get("result"),
        "calculation_payload": _json_object(
            row.get("calculation_payload_json", row.get("calculation_payload", {}))
        ),
        "calculated_at": row.get("calculated_at"),
    }
    result.update({name: _decimal_value(row.get(name)) for name in numeric_fields})
    return result


def _obligation_record(row: Mapping[str, Any]) -> Record:
    return {
        "obligation_id": _uuid_value(row.get("id"), "obligation id"),
        "party_id": _uuid_value(row.get("party_id"), "party id"),
        "lender_name": row.get("lender_name"),
        "obligation_type": str(row.get("obligation_type") or "UNKNOWN").upper(),
        "outstanding_balance": _decimal_value(row.get("outstanding_balance")),
        "monthly_payment": _decimal_value(row.get("monthly_payment")),
        "credit_limit": _decimal_value(row.get("credit_limit")),
        "currency": str(row.get("currency") or ""),
        "verified_status": str(row.get("verified_status") or "UNKNOWN").upper(),
        "source_type": row.get("source_type"),
        "source_id": _optional_uuid(row.get("source_id")),
        "as_of_date": _date_value(row.get("as_of_date")),
    }


def _repayment_metrics(
    calculations: Sequence[Mapping[str, Any]], affordability: Mapping[str, Any] | None
) -> Record:
    metric_names = (
        "monthly_declared_income",
        "monthly_verified_income",
        "monthly_accepted_income",
        "monthly_existing_obligations",
        "projected_monthly_payment",
        "dti",
        "dscr",
        "ltv",
        "net_disposable_income",
        "stress_interest_rate",
        "stress_dti",
    )
    metrics: Record = {
        name.upper(): affordability.get(name)
        for name in metric_names
        if affordability is not None and affordability.get(name) is not None
    }
    payload_metric_names = {
        "dti": "DTI",
        "dscr": "DSCR",
        "ltv": "LTV",
        "net_disposable_income": "NET_DISPOSABLE_INCOME",
        "monthly_existing_obligations": "EXISTING_MONTHLY_OBLIGATIONS",
        "existing_obligations": "EXISTING_MONTHLY_OBLIGATIONS",
        "projected_monthly_payment": "PROJECTED_MONTHLY_PAYMENT",
        "stress_dti": "STRESS_DTI",
        "stress_interest_rate": "STRESS_INTEREST_RATE",
    }
    direct_metrics = frozenset(payload_metric_names.values())
    for calculation in calculations:
        calculation_type = str(calculation.get("calculation_type") or "").upper()
        value = calculation.get("result_value")
        if calculation_type in direct_metrics and value is not None:
            metrics[calculation_type] = value
        if calculation_type != "AFFORDABILITY":
            continue
        payload = calculation.get("result_payload")
        if isinstance(payload, Mapping):
            for key, metric in payload_metric_names.items():
                parsed = _decimal_value(payload.get(key))
                if parsed is not None:
                    metrics[metric] = parsed
        inputs = calculation.get("inputs")
        if isinstance(inputs, Mapping):
            parsed = _decimal_value(inputs.get("existing_obligations"))
            if parsed is not None:
                metrics["EXISTING_MONTHLY_OBLIGATIONS"] = parsed
    return metrics


def _cross_document_conflicts(
    document_rows: Sequence[Mapping[str, Any]],
    field_rows: Sequence[Mapping[str, Any]],
) -> list[Record]:
    document_types = {
        _uuid_value(row.get("document_id"), "document_id"): _normalized_document_type(
            row.get("document_type")
        )
        for row in document_rows
    }
    values_by_field: defaultdict[str, list[Record]] = defaultdict(list)
    selected: set[tuple[UUID, str]] = set()
    for row in sorted(field_rows, key=_field_sort_key):
        document_id = _uuid_value(row.get("document_id"), "document_id")
        field_name = _normalized_field_name(row.get("field_name"))
        if _presence_indicator(field_name) is not None or (document_id, field_name) in selected:
            continue
        value = _effective_field_value(row)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        selected.add((document_id, field_name))
        version_id = _uuid_value(row.get("document_version_id"), "document_version_id")
        values_by_field[field_name].append(
            {
                "document_id": document_id,
                "document_type": document_types.get(
                    document_id,
                    _normalized_document_type(row.get("document_type")),
                ),
                "value": value,
                "comparison_value": _comparison_value(value),
                "evidence": _field_evidence(row, document_id, version_id),
            }
        )

    conflicts: list[Record] = []
    for field_name, values in sorted(values_by_field.items()):
        if len({item["document_id"] for item in values}) < 2:
            continue
        if len({item["comparison_value"] for item in values}) < 2:
            continue
        for item in values:
            item.pop("comparison_value", None)
            item["evidence"]["evidence_role"] = "CONTRADICTING"
        document_names = sorted({str(item["document_type"]) for item in values})
        conflicts.append(
            {
                "field_name": field_name,
                "message": (
                    f"Field '{field_name}' has conflicting recorded values across "
                    f"{', '.join(document_names)}."
                ),
                "values": values,
            }
        )
    return conflicts


def _field_evidence(
    row: Mapping[str, Any], document_id: UUID, document_version_id: UUID
) -> Record:
    return {
        "source_type": "DOCUMENT_FIELD",
        "source_id": _uuid_value(row.get("field_id"), "field_id"),
        "source_locator": {
            "document_id": str(document_id),
            "document_version_id": str(document_version_id),
            "field": _normalized_field_name(row.get("field_name")),
            "page_number": row.get("page_number"),
        },
        "evidence_role": "SUPPORTING",
    }


def _field_sort_key(row: Mapping[str, Any]) -> tuple[str, int, int, str, str]:
    corrected = row.get("corrected_value_text") is not None
    verified = str(row.get("verification_status") or "").upper() == "VERIFIED"
    return (
        str(row.get("document_id") or ""),
        -int(corrected),
        -int(verified),
        _normalized_field_name(row.get("field_name")),
        str(row.get("field_id") or ""),
    )


def _effective_field_value(row: Mapping[str, Any]) -> Any:
    for name in ("corrected_value_text", "normalized_value_text"):
        value = row.get(name)
        if value is not None and (not isinstance(value, str) or value.strip()):
            return value
    value_number = row.get("value_number")
    if value_number is not None:
        return _decimal_value(value_number)
    value_date = row.get("value_date")
    if value_date is not None:
        return _date_value(value_date)
    value = row.get("ocr_value_text")
    if value is not None and (not isinstance(value, str) or value.strip()):
        return value
    return None


def _presence_indicator(field_name: str) -> str | None:
    tokens = set(field_name.split("_"))
    for indicator in _PRESENCE_INDICATORS:
        if indicator in tokens:
            return indicator
    return None


def _presence_value(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    normalized = " ".join(str(value).strip().casefold().replace("_", " ").split())
    if normalized in _TRUE_SIGNALS:
        return True
    if normalized in _FALSE_SIGNALS:
        return False
    return None


def _comparison_value(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, date):
        return value.isoformat()
    return " ".join(str(value).split()).casefold()


def _normalized_document_type(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalized_field_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _uuid_value(value: Any, field_name: str) -> UUID:
    result = _optional_uuid(value)
    if result is None:
        raise ValueError(f"{field_name} must be a UUID")
    return result


def _optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _date_value(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("Persisted date must use ISO format") from exc


def _decimal_value(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, (bool, float)):
        raise TypeError("Persisted financial values must not use bool or binary float")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Persisted financial value is not a decimal") from exc
    if not result.is_finite():
        raise ValueError("Persisted financial value must be finite")
    return result


def _json_object(value: Any) -> Record:
    if value is None:
        return {}
    if isinstance(value, str):
        decoded = json.loads(value, parse_float=Decimal)
    elif isinstance(value, Mapping):
        decoded = dict(value)
    else:
        raise TypeError("Persisted JSON context must be an object")
    if not isinstance(decoded, dict):
        raise TypeError("Persisted JSON context must be an object")
    _reject_binary_floats(decoded)
    return decoded


def _reject_binary_floats(value: Any) -> None:
    if isinstance(value, float):
        raise TypeError("Persisted financial JSON must not use binary float")
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_binary_floats(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_binary_floats(item)
