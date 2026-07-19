from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable

from app.engine.action_recommendation_engine import build_action_plan
from app.schemas.common import Decision, Evidence, Issue, IssueCategory, Severity
from app.schemas.input_ocr_bundle import OCRBundle
from app.schemas.output_report import (
    ActionableFinding,
    BankerView,
    CustomerRequest,
    FindingType,
    FindingSource,
    GroundingStatus,
)


SOURCE_PATTERN = re.compile(
    r"(?P<document>[^#:\s]+)(?:#page=|:)(?P<page>\d+)",
    re.IGNORECASE,
)
TITLE_MARKERS = (
    "BÁO CÁO",
    "GIẤY CHỨNG NHẬN",
    "PHIẾU",
    "HỢP ĐỒNG",
    "CHỨNG THƯ",
    "SAO KÊ",
    "TỜ KHAI",
    "NGHỊ QUYẾT",
    "BẢNG",
    "ĐƠN ",
)


def enrich_issues_with_source_metadata(bundle: OCRBundle, issues: list[Issue]) -> list[Issue]:
    page_map = _page_map(bundle)
    enriched: list[Issue] = []
    for issue in issues:
        key = (issue.location.document_id, issue.location.page_number or 1)
        page = page_map.get(key)
        filename, title = _source_identity(bundle, key, page)
        evidence = [
            item.model_copy(
                update={
                    "source_excerpt": item.source_excerpt
                    or _best_excerpt(_page_for_evidence(item, page_map, page), issue, item)
                }
            )
            for item in issue.evidence
        ]
        enriched.append(
            issue.model_copy(
                update={
                    "location": issue.location.model_copy(
                        update={"source_filename": filename, "document_title": title}
                    ),
                    "evidence": evidence,
                    "why_it_is_an_issue": issue.why_it_is_an_issue or _default_why(issue),
                    "business_impact": issue.business_impact or _default_impact(issue),
                    "resolution_steps": issue.resolution_steps or _resolution_steps(issue),
                    "next_step_after_resolution": issue.next_step_after_resolution
                    or _next_step_after_fix(issue),
                }
            )
        )
    return enriched


def build_banker_view(
    *,
    bundle: OCRBundle,
    issues: list[Issue],
    decision: Decision | None,
    decision_summary: str,
    customer_requests: list[CustomerRequest],
) -> BankerView:
    enriched = enrich_issues_with_source_metadata(bundle, issues)
    findings = build_actionable_findings(bundle, enriched)
    action_plan = build_action_plan(bundle=bundle, findings=findings)
    action_ids_by_finding: dict[str, list[str]] = {}
    for action in action_plan.next_actions:
        for finding_id in action.finding_ids:
            action_ids_by_finding.setdefault(finding_id, []).append(action.action_id)
    findings = [
        item.model_copy(
            update={"recommended_action_ids": action_ids_by_finding.get(item.finding_id, [])}
        )
        for item in findings
    ]
    verified = sum(item.grounding_status == GroundingStatus.VERIFIED for item in findings)
    needing_review = sum(
        item.grounding_status
        in {
            GroundingStatus.PARTIALLY_VERIFIED,
            GroundingStatus.NEEDS_HUMAN_VERIFICATION,
            GroundingStatus.INVALID_SOURCE_REFERENCE,
        }
        for item in findings
    )
    blocking_unverified = any(
        item.severity in {Severity.CRITICAL, Severity.HIGH}
        and item.grounding_status != GroundingStatus.VERIFIED
        for item in findings
    )
    can_submit = (
        decision in {Decision.APPROVE, Decision.APPROVE_WITH_CONDITIONS}
        and not blocking_unverified
        and not action_plan.manual_policy_review_required
    )
    finding_map = {item.finding_id: item for item in findings}
    trusted_customer_requests = []
    for action in action_plan.customer_actions:
        for finding_id in action.finding_ids:
            finding = finding_map.get(finding_id)
            if finding is not None and finding.customer_action:
                trusted_customer_requests.append(finding.customer_action)
    request_list = list(dict.fromkeys(trusted_customer_requests))
    internal_steps = [
        (
            f"{action.owner_role.value}: {action.action_type.value} — "
            f"{action.why_required} [rule {action.source_rule_id}@{action.source_rule_version}]"
        )
        for action in action_plan.internal_actions
    ]
    if not internal_steps:
        internal_steps = [
            "Không có hành động nội bộ phát sinh từ finding đã được grounding và rule còn hiệu lực."
        ]
    if bundle.policy_context is not None:
        checklist_status = "BANK_POLICY_CHECKLIST_PROVIDED"
    elif all(item.document_type.value == "KHAC" for item in bundle.document_manifest.documents):
        checklist_status = "NOT_PROVIDED_OR_DOCUMENTS_UNCLASSIFIED"
    else:
        checklist_status = "MANIFEST_AVAILABLE_REQUIRED_CHECKLIST_NOT_PROVIDED"
    return BankerView(
        decision=decision,
        can_submit_for_approval=can_submit,
        headline=decision_summary,
        total_findings=len(findings),
        critical_findings=sum(item.severity == Severity.CRITICAL for item in findings),
        high_findings=sum(item.severity == Severity.HIGH for item in findings),
        verified_findings=verified,
        findings_needing_human_verification=needing_review,
        findings=findings,
        one_time_customer_request_list=request_list,
        internal_next_steps=internal_steps,
        required_document_checklist_status=checklist_status,
        action_plan=action_plan,
    )


def build_actionable_findings(bundle: OCRBundle, issues: list[Issue]) -> list[ActionableFinding]:
    """Build the same grounded findings used by both decision gating and UI output."""

    return [_to_actionable_finding(bundle, issue) for issue in issues]


def verified_issue_ids(bundle: OCRBundle, issues: list[Issue]) -> set[str]:
    return {
        item.finding_id
        for item in build_actionable_findings(bundle, issues)
        if item.grounding_status == GroundingStatus.VERIFIED
    }


def _to_actionable_finding(bundle: OCRBundle, issue: Issue) -> ActionableFinding:
    page_map = _page_map(bundle)
    sources: list[FindingSource] = []
    statuses: list[GroundingStatus] = []
    seen: set[tuple[str, int]] = set()
    for evidence in issue.evidence:
        parsed = _parse_source(evidence.source)
        if parsed is None:
            key = (issue.location.document_id, issue.location.page_number or 1)
        else:
            key = parsed
        if key in seen:
            continue
        seen.add(key)
        page = page_map.get(key)
        if page is None:
            statuses.append(GroundingStatus.INVALID_SOURCE_REFERENCE)
            continue
        filename, title = _source_identity(bundle, key, page)
        excerpt = evidence.source_excerpt or _best_excerpt(page, issue, evidence)
        status = _grounding_status(page.ocr_text, excerpt, evidence)
        statuses.append(status)
        sources.append(
            FindingSource(
                document_id=key[0],
                source_filename=filename,
                document_title=title,
                page_number=key[1],
                field_name=issue.location.field_name,
                source_excerpt=excerpt,
                extraction_confidence=page.ocr_confidence,
            )
        )
    if not sources:
        key = (issue.location.document_id, issue.location.page_number or 1)
        page = page_map.get(key)
        if page is not None:
            filename, title = _source_identity(bundle, key, page)
            excerpt = _best_excerpt(page, issue, issue.evidence[0])
            sources.append(
                FindingSource(
                    document_id=key[0],
                    source_filename=filename,
                    document_title=title,
                    page_number=key[1],
                    field_name=issue.location.field_name,
                    source_excerpt=excerpt,
                    extraction_confidence=page.ocr_confidence,
                )
            )
            statuses.append(GroundingStatus.NEEDS_HUMAN_VERIFICATION)

    grounding_status = _combine_statuses(statuses)
    bank_policy_can_authorize_customer_request = bool(
        bundle.policy_context is not None
        and bundle.policy_context.policy_id
        and bundle.policy_context.effective_from
        and issue.category.value in bundle.policy_context.action_rule_sections
    )
    return ActionableFinding(
        finding_id=issue.issue_id,
        category=issue.category,
        severity=issue.severity,
        finding_type=_finding_type(issue),
        what_is_wrong=issue.description,
        why_it_is_an_issue=issue.why_it_is_an_issue or _default_why(issue),
        business_impact=issue.business_impact or _default_impact(issue),
        sources=sources,
        grounding_status=grounding_status,
        decision_effect=_decision_effect(issue, grounding_status),
        customer_action=(
            issue.suggested_customer_action
            if grounding_status == GroundingStatus.VERIFIED
            and bank_policy_can_authorize_customer_request
            else None
        ),
        internal_action=(
            "Đối chiếu trực tiếp tài liệu gốc và xác nhận lại finding."
            if _combine_statuses(statuses) != GroundingStatus.VERIFIED
            else "Xác nhận finding, liên kết chứng từ bổ sung và cập nhật trạng thái xử lý."
        ),
        next_step_after_fix=issue.next_step_after_resolution or _next_step_after_fix(issue),
    )


def _page_map(bundle: OCRBundle):
    return {(page.document_id, page.page_number): page for page in bundle.ocr_pages}


def _page_for_evidence(evidence: Evidence, page_map: dict, fallback):
    parsed = _parse_source(evidence.source)
    return page_map.get(parsed, fallback) if parsed is not None else fallback


def _parse_source(source: str) -> tuple[str, int] | None:
    match = SOURCE_PATTERN.search(source)
    if match is None:
        return None
    return match.group("document"), int(match.group("page"))


def _source_identity(bundle: OCRBundle, key: tuple[str, int], page) -> tuple[str, str]:
    manifest = next(
        (item for item in bundle.document_manifest.documents if item.document_id == key[0]),
        None,
    )
    page_filename = page.ocr_fields.get("source_filename") if page else None
    filename = (
        (manifest.source_filename if manifest else None)
        or (str(page_filename) if page_filename else "")
        or key[0]
    )
    title = (manifest.document_title if manifest else None) or _infer_title(
        page.ocr_text if page else ""
    )
    return filename, title


def _infer_title(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 4]
    for line in lines[:30]:
        upper = line.upper()
        if any(marker in upper for marker in TITLE_MARKERS):
            return line[:180]
    return (lines[0][:180] if lines else "Không xác định được tiêu đề tài liệu")


def _best_excerpt(page, issue: Issue, evidence: Evidence) -> str:
    if page is None:
        return "Không tìm thấy trang nguồn trong OCR Bundle."
    lines = [line.strip() for line in page.ocr_text.splitlines() if line.strip()]
    if not lines:
        return "Trang không có OCR text."
    target_tokens = _tokens(issue.description)
    target_tokens.update(_tokens(json.dumps(evidence.value, ensure_ascii=False)))
    best = max(lines, key=lambda line: _overlap_score(target_tokens, _tokens(line)))
    index = lines.index(best)
    selected = lines[max(0, index - 1) : min(len(lines), index + 2)]
    return " | ".join(selected)[:500]


def _grounding_status(text: str, excerpt: str, evidence: Evidence) -> GroundingStatus:
    normalized_text = _normalize(text)
    normalized_excerpt = _normalize(excerpt)
    excerpt_is_from_source = bool(normalized_excerpt and normalized_excerpt in normalized_text)
    values = [value for value in _flatten_values(evidence.value) if len(_normalize(value)) >= 2]
    matched_values = [value for value in values if _normalize(value) in normalized_text]
    evidence_tokens = _tokens(json.dumps(evidence.value, ensure_ascii=False))
    excerpt_tokens = _tokens(excerpt)
    contextual_tokens = excerpt_tokens - evidence_tokens
    if matched_values and excerpt_is_from_source and contextual_tokens:
        return GroundingStatus.VERIFIED
    if matched_values and excerpt_is_from_source:
        return GroundingStatus.PARTIALLY_VERIFIED
    if excerpt_is_from_source and _overlap_score(evidence_tokens, excerpt_tokens) >= 0.25:
        return GroundingStatus.PARTIALLY_VERIFIED
    return GroundingStatus.NEEDS_HUMAN_VERIFICATION


def _flatten_values(value) -> Iterable[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _flatten_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _flatten_values(item)
    elif value is not None:
        yield str(value)


def _combine_statuses(statuses: list[GroundingStatus]) -> GroundingStatus:
    if not statuses or GroundingStatus.INVALID_SOURCE_REFERENCE in statuses:
        return GroundingStatus.INVALID_SOURCE_REFERENCE
    if all(status == GroundingStatus.VERIFIED for status in statuses):
        return GroundingStatus.VERIFIED
    if any(status == GroundingStatus.VERIFIED for status in statuses) or any(
        status == GroundingStatus.PARTIALLY_VERIFIED for status in statuses
    ):
        return GroundingStatus.PARTIALLY_VERIFIED
    return GroundingStatus.NEEDS_HUMAN_VERIFICATION


def _default_why(issue: Issue) -> str:
    return {
        IssueCategory.HARD_STOP: "Vấn đề có thể làm hồ sơ không đáp ứng điều kiện pháp lý hoặc điều kiện cấp tín dụng bắt buộc.",
        IssueCategory.CIC_RED_FLAG: "Thông tin tín dụng cho thấy rủi ro về lịch sử trả nợ hoặc nghĩa vụ nợ chưa được giải trình.",
        IssueCategory.FINANCIAL_LOGIC_FAIL: "Số liệu ảnh hưởng trực tiếp đến khả năng trả nợ và phải được tính lại từ nguồn đã xác minh.",
        IssueCategory.CROSS_CHECK_MISMATCH: "Các tài liệu không cùng thể hiện một sự thật; chưa thể xác định dữ liệu nào là chính thức.",
        IssueCategory.MINOR_DISCREPANCY: "Sai lệch dữ liệu cần được chỉnh để hồ sơ và chứng từ nhất quán.",
        IssueCategory.MISSING_DOCUMENT: "Thiếu chứng từ hoặc dữ liệu cần thiết để hoàn tất bước kiểm tra tương ứng.",
        IssueCategory.PRE_DISBURSEMENT_CONDITION: "Đây là điều kiện phải hoàn thành trước giải ngân, không tự động đồng nghĩa với từ chối hồ sơ.",
        IssueCategory.POLICY_REVIEW_REQUIRED: "Finding chưa khớp một quy tắc quyết định đã được ngân hàng phê duyệt và cần chuyên viên phân loại.",
    }[issue.category]


def _finding_type(issue: Issue) -> FindingType:
    return {
        IssueCategory.HARD_STOP: FindingType.POLICY_BLOCKER,
        IssueCategory.CIC_RED_FLAG: FindingType.RISK_SIGNAL,
        IssueCategory.FINANCIAL_LOGIC_FAIL: FindingType.FINANCIAL_ERROR,
        IssueCategory.CROSS_CHECK_MISMATCH: FindingType.CONTRADICTION,
        IssueCategory.MINOR_DISCREPANCY: FindingType.DATA_QUALITY_ERROR,
        IssueCategory.MISSING_DOCUMENT: FindingType.MISSING_INFORMATION,
        IssueCategory.PRE_DISBURSEMENT_CONDITION: FindingType.PRE_DISBURSEMENT_CONDITION,
        IssueCategory.POLICY_REVIEW_REQUIRED: FindingType.REQUIRES_POLICY_CLASSIFICATION,
    }[issue.category]


def _decision_effect(issue: Issue, status: GroundingStatus) -> str:
    if status != GroundingStatus.VERIFIED:
        return "Không được dùng để APPROVE hoặc REJECT tự động; phải xác minh tài liệu gốc trước."
    if issue.category == IssueCategory.HARD_STOP and issue.severity == Severity.CRITICAL:
        return "Có thể kích hoạt REJECT khi khớp quy tắc Hard Stop đã được ngân hàng phê duyệt."
    if issue.category == IssueCategory.PRE_DISBURSEMENT_CONDITION:
        return "Là điều kiện trước giải ngân; theo dõi đến khi hoàn thành, không tự động từ chối."
    if issue.category == IssueCategory.MISSING_DOCUMENT:
        return "Giữ hồ sơ ở PENDING đến khi nhận và kiểm tra tài liệu bổ sung."
    return "Đưa vào đánh giá tổng thể; không tự mình quyết định kết quả tín dụng."


def _default_impact(issue: Issue) -> str:
    if issue.severity == Severity.CRITICAL:
        return "Có thể làm thay đổi quyết định tín dụng; không được bỏ qua trước khi trình phê duyệt."
    if issue.severity == Severity.HIGH:
        return "Có thể làm sai đánh giá rủi ro, nghĩa vụ nợ hoặc khả năng trả nợ."
    if issue.severity == Severity.MEDIUM:
        return "Cần được giải trình để giảm rủi ro hồ sơ thiếu nhất quán."
    return "Không quyết định khoản vay một mình nhưng cần chỉnh để hoàn thiện hồ sơ."


def _resolution_steps(issue: Issue) -> list[str]:
    if issue.suggested_customer_action:
        return [issue.suggested_customer_action]
    return ["Chuyên viên đối chiếu tài liệu gốc và yêu cầu chứng từ/giải trình phù hợp nếu finding được xác nhận."]


def _next_step_after_fix(issue: Issue) -> str:
    return (
        "Cập nhật text/dữ liệu đã trích xuất kèm nguồn và trang, chạy lại assessment, "
        "xác nhận finding đã RESOLVED rồi mới trình phê duyệt."
    )


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.replace("đ", "d").replace("Đ", "D"))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("đ", "d"))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return {token for token in re.findall(r"[a-z0-9]+", normalized) if len(token) >= 2}


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)
