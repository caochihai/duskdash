"""Conservative deterministic document completeness and consistency checks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.agents.base import (
    AgentInput,
    AgentName,
    AgentOutput,
    DownstreamReadiness,
    EvidenceReference,
    EvidenceRole,
    FindingDraft,
)

_PRESENCE_INDICATORS = frozenset({"signature", "seal", "stamp"})


class DocumentAgent:
    """Evaluate recorded document signals without making authenticity claims."""

    name = AgentName.DOCUMENT

    async def run(self, request: AgentInput) -> AgentOutput:
        context = request.context
        required = {_normalize_type(item) for item in _strings(context.get("required_document_types"))}
        supplied_evidence = tuple(
            _evidence(context.get("evidence", ()), request.authorized_source_ids)
        )
        evidence_by_source = {item.source_id: item for item in supplied_evidence}
        documents = _documents(context.get("documents"), request.authorized_source_ids)
        available = {
            _normalize_type(item) for item in _strings(context.get("available_document_types"))
        }
        available.update(document["document_type"] for document in documents)
        missing = sorted(required - available)
        findings: list[FindingDraft] = []
        contradictions: list[str] = []
        missing_information: list[str] = list(missing)
        risk_flags: set[str] = set()

        if missing:
            findings.append(
                FindingDraft(
                    finding_type="MISSING_DOCUMENT",
                    title="Required documents are missing",
                    description=f"Missing document types: {', '.join(missing)}.",
                    severity="HIGH",
                    confidence=Decimal("1.0"),
                    recommended_action="Collect and verify the missing documents.",
                    evidence=supplied_evidence,
                )
            )
            risk_flags.add("MISSING_REQUIRED_DOCUMENT")

        assessment_date = _assessment_date(context.get("assessment_date"))
        indicator_requirements = _indicator_requirements(
            context.get("required_document_indicators")
            or context.get("required_presence_indicators")
        )
        for document in documents:
            reference = _document_evidence(document, evidence_by_source)
            document_type = document["document_type"]
            raw_status = document.get("verification_status")
            if raw_status is None and isinstance(document.get("is_verified"), bool):
                raw_status = "VERIFIED" if document["is_verified"] else "UNVERIFIED"
            status = str(raw_status or "UNVERIFIED").strip().upper()
            if status != "VERIFIED":
                findings.append(
                    FindingDraft(
                        finding_type="UNVERIFIED_DOCUMENT",
                        title=f"{document_type} has not been human verified",
                        description=(
                            f"{document_type} has recorded verification status {status or 'UNVERIFIED'}."
                        ),
                        severity="HIGH" if status == "REJECTED" else "MEDIUM",
                        confidence=Decimal("1"),
                        recommended_action="Complete authorized human verification.",
                        evidence=(reference,),
                    )
                )
                risk_flags.add("UNVERIFIED_DOCUMENT")

            raw_expiry = _first_present(document, ("expiry_date", "expires_on", "expires_at"))
            expiry_date = _optional_date(raw_expiry, "document expiry date")
            recorded_expired = document.get("is_expired")
            expired = recorded_expired is True or (
                expiry_date is not None
                and assessment_date is not None
                and expiry_date < assessment_date
            )
            if expiry_date is not None and assessment_date is None and recorded_expired is None:
                item = f"assessment_date required to evaluate {document_type} expiry"
                if item not in missing_information:
                    missing_information.append(item)
            if expired:
                findings.append(
                    FindingDraft(
                        finding_type="EXPIRED_DOCUMENT",
                        title=f"{document_type} is expired",
                        description=f"{document_type} is recorded as expired for this assessment.",
                        severity="HIGH",
                        confidence=Decimal("1"),
                        recommended_action="Obtain a current document and verify it.",
                        evidence=(reference,),
                    )
                )
                risk_flags.add("EXPIRED_DOCUMENT")

            required_indicators = set(indicator_requirements.get(document_type, ()))
            required_indicators.update(_indicator_names(document.get("required_indicators")))
            recorded_indicators = _indicator_values(document)
            for indicator in sorted(required_indicators):
                presence = recorded_indicators.get(indicator)
                if presence is True:
                    continue
                if presence is False:
                    finding_type = "DOCUMENT_INDICATOR_NOT_PRESENT"
                    description = (
                        f"The recorded {indicator} presence signal for {document_type} is false."
                    )
                    risk_flags.add(f"MISSING_{indicator.upper()}_INDICATOR")
                else:
                    finding_type = "DOCUMENT_INDICATOR_UNCONFIRMED"
                    description = (
                        f"No confirmed {indicator} presence signal is recorded for {document_type}."
                    )
                    item = f"{document_type} {indicator} presence signal"
                    if item not in missing_information:
                        missing_information.append(item)
                findings.append(
                    FindingDraft(
                        finding_type=finding_type,
                        title=f"{document_type} {indicator} requires review",
                        description=description,
                        severity="MEDIUM",
                        confidence=Decimal("1"),
                        recommended_action=(
                            "Ask an authorized reviewer to inspect the original document; the signal "
                            "does not establish legal authenticity."
                        ),
                        evidence=(reference,),
                    )
                )

            for field_name, _, field_status, _ in _field_entries(document):
                if field_status is None or field_status == "VERIFIED":
                    continue
                locator = dict(reference.source_locator)
                locator["field"] = field_name
                findings.append(
                    FindingDraft(
                        finding_type="UNVERIFIED_DOCUMENT_FIELD",
                        title=f"{document_type} field {field_name} is not verified",
                        description=(
                            f"{document_type} field '{field_name}' has recorded verification status "
                            f"{field_status}."
                        ),
                        severity="MEDIUM",
                        confidence=Decimal("1"),
                        recommended_action="Verify the cited extracted field against the source document.",
                        evidence=(reference.model_copy(update={"source_locator": locator}),),
                    )
                )
                risk_flags.add("UNVERIFIED_EXTRACTED_FIELD")

        conflict_findings, conflict_messages = _cross_document_conflicts(
            documents, evidence_by_source
        )
        if conflict_findings:
            findings.extend(conflict_findings)
            contradictions.extend(conflict_messages)
            risk_flags.add("CROSS_DOCUMENT_CONFLICT")

        issues = _strings(context.get("document_issues"))
        if issues:
            findings.append(
                FindingDraft(
                    finding_type="DOCUMENT_ISSUE",
                    title="Documents require human review",
                    description="; ".join(issues),
                    severity="MEDIUM",
                    confidence=Decimal("0.95"),
                    recommended_action="Assign an authorized document reviewer.",
                    evidence=supplied_evidence,
                )
            )

        if required and not missing and supplied_evidence:
            findings.append(
                FindingDraft(
                    finding_type="DOCUMENT_COMPLETENESS",
                    title="Required document types are present",
                    description=(
                        "All document types required by the supplied analysis context are present; "
                        "this completeness signal does not establish authenticity."
                    ),
                    severity="INFO",
                    confidence=Decimal("1"),
                    recommended_action=(
                        "Continue evidence validation and authorized human document review."
                    ),
                    evidence=supplied_evidence,
                )
            )

        all_evidence = _unique_evidence(
            (*supplied_evidence, *(item for finding in findings for item in finding.evidence))
        )
        return AgentOutput(
            agent_name=self.name,
            task_id=request.task_id,
            conclusion=(
                "Document completeness, recorded verification state, visual presence indicators, "
                "and cross-document consistency were assessed; legal authenticity was not determined."
            ),
            findings=tuple(findings),
            evidence_references=all_evidence,
            downstream_readiness=DownstreamReadiness(
                credit_context_ready=not missing,
                compliance_context_ready=not missing,
                blockers=tuple(
                    f"required document type is missing: {document_type}"
                    for document_type in missing
                ),
            ),
            missing_information=tuple(missing_information),
            contradictions=tuple(contradictions),
            risk_flags=tuple(sorted(risk_flags)),
            limitations=(
                "Signature, seal, and stamp checks report recorded presence signals only; they do not "
                "establish legal authenticity or prove that a document is genuine.",
                "Authenticity and fraud determinations require an authorized human or qualified "
                "verification service.",
            ),
            recommended_action=(
                "Resolve document findings and conflicts before synthesis."
                if findings
                else "Continue analysis while retaining human document review."
            ),
            confidence=Decimal("0.95") if all_evidence else Decimal("0.70"),
        )


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    return tuple(str(item) for item in value)


def _normalize_type(value: object) -> str:
    return str(value).strip().upper()


def _evidence(value: object, authorized: frozenset[UUID]) -> list[EvidenceReference]:
    if not isinstance(value, (list, tuple)):
        return []
    references = [EvidenceReference.model_validate(item) for item in value]
    unauthorized = [reference.source_id for reference in references if reference.source_id not in authorized]
    if unauthorized:
        raise PermissionError("document evidence is outside the authorized analysis scope")
    return references


def _documents(value: object, authorized: frozenset[UUID]) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("documents must be a list")
    documents: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ValueError("each document must be an object")
        document_type = _normalize_type(raw.get("document_type", ""))
        if not document_type:
            raise ValueError("document_type is required")
        try:
            source_id = UUID(str(raw["source_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("document source_id must be a UUID") from exc
        if source_id not in authorized:
            raise PermissionError("document is outside the authorized analysis scope")
        document = dict(raw)
        document["document_type"] = document_type
        document["source_id"] = source_id
        documents.append(document)
    return tuple(documents)


def _assessment_date(value: object) -> date | None:
    return _optional_date(value, "assessment_date")


def _optional_date(value: object, name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO date") from exc


def _indicator_requirements(value: object) -> dict[str, tuple[str, ...]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("required_document_indicators must be an object")
    return {
        _normalize_type(document_type): _indicator_names(indicators)
        for document_type, indicators in value.items()
    }


def _indicator_names(value: object) -> tuple[str, ...]:
    indicators = tuple(item.strip().lower() for item in _strings(value))
    invalid = sorted(set(indicators) - _PRESENCE_INDICATORS)
    if invalid:
        raise ValueError(f"unsupported document presence indicators: {', '.join(invalid)}")
    return indicators


def _indicator_values(document: Mapping[str, Any]) -> dict[str, bool | None]:
    nested = document.get("presence_indicators")
    if nested is not None and not isinstance(nested, Mapping):
        raise ValueError("presence_indicators must be an object")
    value = nested if isinstance(nested, Mapping) else {}
    result: dict[str, bool | None] = {}
    for raw_name, raw_presence in value.items():
        name = str(raw_name).strip().lower()
        if name not in _PRESENCE_INDICATORS:
            raise ValueError(f"unsupported document presence indicator: {name}")
        if raw_presence is not None and not isinstance(raw_presence, bool):
            raise ValueError(f"{name} presence indicator must be true, false, or null")
        result[name] = raw_presence
    aliases = {
        "signature": ("signature_present", "has_signature"),
        "seal": ("seal_present", "has_seal"),
        "stamp": ("stamp_present", "has_stamp", "red_stamp_present"),
    }
    for indicator, keys in aliases.items():
        if indicator in result:
            continue
        presence = _first_present(document, keys)
        if presence is not None and not isinstance(presence, bool):
            raise ValueError(f"{indicator} presence indicator must be true, false, or null")
        if presence is not None or any(key in document for key in keys):
            result[indicator] = presence
    return result


def _document_evidence(
    document: Mapping[str, Any], supplied: Mapping[UUID, EvidenceReference]
) -> EvidenceReference:
    source_id = document["source_id"]
    reference = supplied.get(source_id)
    if reference is not None:
        return reference
    return EvidenceReference(
        source_type="DOCUMENT_VERSION",
        source_id=source_id,
        source_locator={"document_type": document["document_type"]},
    )


def _cross_document_conflicts(
    documents: tuple[dict[str, Any], ...], supplied: Mapping[UUID, EvidenceReference]
) -> tuple[list[FindingDraft], list[str]]:
    fields: defaultdict[str, list[tuple[str, str, EvidenceReference]]] = defaultdict(list)
    for document in documents:
        for field_name, raw_value, _, field_source_id in _field_entries(document):
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                continue
            normalized_value = " ".join(str(raw_value).split()).casefold()
            base_reference = (
                supplied.get(field_source_id)
                if field_source_id is not None
                else None
            ) or _document_evidence(document, supplied)
            locator = dict(base_reference.source_locator)
            locator.update({"document_type": document["document_type"], "field": field_name})
            fields[field_name].append(
                (
                    document["document_type"],
                    normalized_value,
                    base_reference.model_copy(
                        update={
                            "source_locator": locator,
                            "evidence_role": EvidenceRole.CONTRADICTING,
                        }
                    ),
                )
            )

    findings: list[FindingDraft] = []
    contradictions: list[str] = []
    for field_name, values in sorted(fields.items()):
        if len({value for _, value, _ in values}) < 2:
            continue
        document_types = sorted({document_type for document_type, _, _ in values})
        message = (
            f"Field '{field_name}' has conflicting recorded values across "
            f"{', '.join(document_types)}."
        )
        contradictions.append(message)
        findings.append(
            FindingDraft(
                finding_type="CROSS_DOCUMENT_FIELD_CONFLICT",
                title=f"Conflicting {field_name} across documents",
                description=message,
                severity="HIGH",
                confidence=Decimal("1"),
                recommended_action=(
                    "Compare the cited document versions and resolve the value through authorized "
                    "human verification."
                ),
                evidence=tuple(reference for _, _, reference in values),
            )
        )
    return findings, contradictions


def _field_entries(
    document: Mapping[str, Any],
) -> tuple[tuple[str, object, str | None, UUID | None], ...]:
    extracted = document.get("extracted_fields", {})
    entries: list[tuple[str, object, str | None, UUID | None]] = []
    if isinstance(extracted, Mapping):
        for raw_name, raw_value in extracted.items():
            status: str | None = None
            source_id: UUID | None = None
            value = raw_value
            if isinstance(raw_value, Mapping):
                value = _first_present(
                    raw_value,
                    (
                        "normalized_value_text",
                        "value_text",
                        "value_number",
                        "value_date",
                        "value_boolean",
                        "value",
                    ),
                )
                raw_status = raw_value.get("verification_status")
                status = str(raw_status).strip().upper() if raw_status is not None else None
                source_id = _optional_uuid(raw_value.get("source_id"))
            entries.append((str(raw_name).strip(), value, status, source_id))
        return tuple(entries)
    if not isinstance(extracted, (list, tuple)):
        raise ValueError("extracted_fields must be an object or list")
    for raw_field in extracted:
        if not isinstance(raw_field, Mapping):
            raise ValueError("each extracted field must be an object")
        field_name = str(raw_field.get("field_name", "")).strip()
        if not field_name:
            raise ValueError("extracted field_name is required")
        value = _first_present(
            raw_field,
            (
                "normalized_value_text",
                "value_text",
                "value_number",
                "value_date",
                "value_boolean",
                "value",
            ),
        )
        raw_status = raw_field.get("verification_status")
        status = str(raw_status).strip().upper() if raw_status is not None else None
        entries.append((field_name, value, status, _optional_uuid(raw_field.get("source_id"))))
    return tuple(entries)


def _optional_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("extracted field source_id must be a UUID") from exc


def _first_present(value: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return None


def _unique_evidence(value: tuple[EvidenceReference, ...]) -> tuple[EvidenceReference, ...]:
    unique: dict[tuple[UUID, str], EvidenceReference] = {}
    for reference in value:
        key = (reference.source_id, repr(sorted(reference.source_locator.items())))
        unique.setdefault(key, reference)
    return tuple(unique.values())
