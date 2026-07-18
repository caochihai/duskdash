from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.schemas.common import Evidence, Issue, IssueCategory, IssueLocation, Severity
from app.schemas.input_ocr_bundle import OCRBundle, OCRPage


@dataclass(frozen=True)
class FieldValue:
    field_name: str
    value: str
    document_id: str
    page_number: int
    excerpt: str


def detect_structured_cross_checks(bundle: OCRBundle, existing: list[Issue]) -> list[Issue]:
    """Deterministically catch high-value identity/date mismatches across documents."""

    customer_ids: list[FieldValue] = []
    customer_birth_dates: list[FieldValue] = []
    spouse_birth_dates: list[FieldValue] = []
    business_start_dates: list[FieldValue] = []
    for page in bundle.ocr_pages:
        lines = [line.strip() for line in page.ocr_text.splitlines() if line.strip()]
        normalized = [_normalize(line) for line in lines]
        if _is_primary_customer_page(normalized):
            value = _extract_after_labels(
                page,
                lines,
                normalized,
                ("so giay to", "so cccd", "so cmndicccd", "so cccdicccd"),
                r"\b\d{12}\b",
                stop_markers=("thong tin vo", "xac minh dang ky ket hon"),
            )
            if value:
                customer_ids.append(FieldValue("citizen_id", *value))
            value = _extract_after_labels(
                page,
                lines,
                normalized,
                ("ngay sinh", "sinh ngay"),
                r"\b\d{2}/\d{2}/\d{4}\b",
                stop_markers=("thong tin vo", "xac minh dang ky ket hon"),
            )
            if value:
                customer_birth_dates.append(FieldValue("date_of_birth", *value))

        spouse_start = _find_spouse_section(normalized)
        if spouse_start is not None:
            value = _extract_after_labels(
                page,
                lines[spouse_start:],
                normalized[spouse_start:],
                ("ngay sinh", "sinh ngay", "nam sinh"),
                r"\b\d{2}/\d{2}/\d{4}\b",
            )
            if value:
                spouse_birth_dates.append(FieldValue("spouse_date_of_birth", *value))

        value = _extract_after_labels(
            page,
            lines,
            normalized,
            ("thoi diem bat dau hoat dong", "ngay bat dau kinh doanh"),
            r"\b\d{2}/\d{2}/\d{4}\b",
        )
        if value:
            business_start_dates.append(FieldValue("business_start_date", *value))

    findings: list[Issue] = []
    for field_name, label, values, severity in (
        ("citizen_id", "Số CCCD khách hàng", customer_ids, Severity.HIGH),
        ("date_of_birth", "Ngày sinh khách hàng", customer_birth_dates, Severity.HIGH),
        ("spouse_date_of_birth", "Ngày sinh người phối ngẫu", spouse_birth_dates, Severity.MEDIUM),
        ("business_start_date", "Ngày bắt đầu kinh doanh", business_start_dates, Severity.MEDIUM),
    ):
        issue = _build_mismatch(field_name, label, values, severity, existing + findings)
        if issue is not None:
            findings.append(issue)
    return findings


def _build_mismatch(
    field_name: str,
    label: str,
    values: list[FieldValue],
    severity: Severity,
    existing: list[Issue],
) -> Issue | None:
    unique = list(dict.fromkeys(item.value for item in values))
    if len(unique) < 2:
        return None
    if any(
        issue.location.field_name == field_name
        or all(value in _normalize(issue.description) for value in unique)
        for issue in existing
    ):
        return None
    selected = [next(item for item in values if item.value == value) for value in unique[:3]]
    first = selected[0]
    return Issue(
        issue_id=f"DET-{field_name.upper()}",
        category=IssueCategory.CROSS_CHECK_MISMATCH,
        severity=severity,
        location=IssueLocation(
            document_id=first.document_id,
            page_number=first.page_number,
            field_name=field_name,
        ),
        description=f"{label} không nhất quán giữa các tài liệu: "
        + "; ".join(f"{item.document_id} ghi {item.value}" for item in selected)
        + ".",
        why_it_is_an_issue=f"{label} là trường đối chiếu bắt buộc; các tài liệu phải cùng thể hiện một giá trị.",
        business_impact="Chưa thể xác định dữ liệu chính thức để lập hồ sơ/hợp đồng; cần đối chiếu bản gốc.",
        evidence=[
            Evidence(
                source=f"{item.document_id}#page={item.page_number}",
                value=item.value,
                source_excerpt=item.excerpt,
            )
            for item in selected
        ],
        requires_customer_action=True,
        suggested_customer_action=f"Cung cấp tài liệu gốc xác nhận {label.lower()} và chỉnh các tài liệu sai.",
        resolution_steps=[
            "Đối chiếu tài liệu gốc với dữ liệu định danh/đăng ký chính thức.",
            "Cập nhật tất cả chứng từ dùng cùng một giá trị đã xác minh.",
        ],
        next_step_after_resolution="Chạy lại cross-check, xác nhận mismatch đã RESOLVED rồi mới lập hợp đồng/trình phê duyệt.",
        confidence=1.0,
    )


def _is_primary_customer_page(lines: list[str]) -> bool:
    top = " ".join(lines[:45])
    if "thu nhap cua chong" in top:
        return False
    return any(
        marker in top
        for marker in ("thong tin khach hang", "thong tin ho kinh doanh", "thong tin chu tai khoan")
    )


def _find_spouse_section(lines: list[str]) -> int | None:
    top = " ".join(lines[:35])
    if "thu nhap cua chong" in top:
        return 0
    return next(
        (index for index, line in enumerate(lines) if "thong tin voichong" in line or "thong tin vo/chong" in line),
        None,
    )


def _extract_after_labels(
    page: OCRPage,
    lines: list[str],
    normalized: list[str],
    labels: tuple[str, ...],
    value_pattern: str,
    *,
    stop_markers: tuple[str, ...] = (),
) -> tuple[str, str, int, str] | None:
    for index, line in enumerate(normalized):
        if stop_markers and any(marker in line for marker in stop_markers):
            return None
        if not any(label in line for label in labels):
            continue
        nearby = lines[index : min(len(lines), index + 4)]
        match = re.search(value_pattern, " ".join(nearby))
        if match:
            return match.group(0), page.document_id, page.page_number, " | ".join(nearby)
    return None


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("đ", "d"))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized).strip()
