"""Compose Agent — tổng hợp báo cáo + VERIFY chống bịa nguồn (rủi ro #2).

Bất biến: không luận điểm nào tồn tại ở báo cáo tổng hợp nếu citation của nó không
resolve về một Citation gốc do specialist tạo. Citation lạ → loại, luận điểm hạ cấp
thành `unsupported` và ghi ra `unsupported_claims` (minh bạch, không giấu).
"""

from __future__ import annotations

from uuid import UUID

from libs.contracts import (
    ComposedClaim,
    ComposedReport,
    ComposedSection,
    Domain,
    DomainReport,
    ReportStatus,
    collect_citations,
)

from . import llm

_DOMAIN_TITLE = {
    Domain.CREDIT: "Phân tích tài chính",
    Domain.LEGAL: "Tuân thủ pháp lý",
    Domain.DOCUMENT: "Đối chiếu hồ sơ",
}


def verify_claim(citation_ids: tuple[str, ...], known_ids: set[str]) -> tuple[tuple[str, ...], bool]:
    """Giữ lại các citation resolve được; trả (ids_hợp_lệ, supported).

    supported=False khi luận điểm có tham chiếu nguồn NHƯNG không cái nào resolve.
    """
    valid = tuple(cid for cid in citation_ids if cid in known_ids)
    if citation_ids and not valid:
        return (), False
    return valid, True


async def compose(
    correlation_id: UUID,
    question: str,
    reports: list[DomainReport],
) -> ComposedReport:
    all_citations = collect_citations(reports)
    known_ids = {c.id for c in all_citations}

    sections: list[ComposedSection] = []
    unsupported: list[str] = []

    for report in reports:
        composed_claims: list[ComposedClaim] = []
        for claim in report.claims:
            valid_ids, supported = verify_claim(claim.citation_ids, known_ids)
            if not supported:
                unsupported.append(claim.text)
                composed_claims.append(ComposedClaim(
                    text=claim.text + "  [chưa có nguồn xác thực]",
                    citation_ids=(), supported=False))
            else:
                composed_claims.append(ComposedClaim(
                    text=claim.text, citation_ids=valid_ids, supported=True))
        sections.append(ComposedSection(
            title=_DOMAIN_TITLE.get(report.domain, report.domain.value),
            domain=report.domain, claims=tuple(composed_claims)))

    recommendation = await _recommend(question, reports)
    warnings = _warnings(reports)

    return ComposedReport(
        correlation_id=correlation_id,
        question=question,
        recommendation=recommendation,
        sections=tuple(sections),
        citations=all_citations,
        unsupported_claims=tuple(unsupported),
        domain_status={r.domain.value: r.status for r in reports},
        warnings=warnings,
    )


async def _recommend(question: str, reports: list[DomainReport]) -> str:
    ok = [r for r in reports if r.status != ReportStatus.FAILED]
    bullets = "\n".join(f"- [{r.domain.value}] {r.summary}" for r in ok if r.summary)
    return await llm.narrate(
        system="Bạn là cán bộ thẩm định tổng hợp. Đưa khuyến nghị phê duyệt/điều kiện "
               "trong 2-3 câu, chỉ dựa trên tóm tắt các lĩnh vực, không thêm số liệu mới.",
        user=f"Câu hỏi thẩm định: {question}\nTóm tắt các lĩnh vực:\n{bullets}",
    )


def _warnings(reports: list[DomainReport]) -> tuple[str, ...]:
    w: list[str] = []
    for r in reports:
        if r.status == ReportStatus.FAILED:
            w.append(f"Lĩnh vực {r.domain.value} lỗi: {r.error or 'không rõ'} — báo cáo thiếu phần này.")
        elif r.status == ReportStatus.PARTIAL:
            w.append(f"Lĩnh vực {r.domain.value} chỉ có kết quả một phần.")
    return tuple(w)
