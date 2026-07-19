"""Báo cáo lĩnh vực & báo cáo tổng hợp — xương sống đánh nguồn kiểu NotebookLM.

Bất biến bắt buộc (chống bịa nguồn):
- Trong `DomainReport`: mọi `citation_id` mà một `Claim` tham chiếu PHẢI khớp
  `Citation.id` có thật trong `citations` của chính báo cáo đó.
- Ở `ComposedReport`: mọi `citation_id` của luận điểm tổng hợp PHẢI truy được về
  một `Citation` gốc do specialist tạo (verify ở tầng Compose). Citation không
  resolve được bị loại và luận điểm đánh dấu `unsupported`.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from libs.contracts._enum import StrEnum
from libs.contracts.citation import Citation


class Domain(StrEnum):
    CREDIT = "CREDIT"      # tài chính (REAL, +SQL tool)
    LEGAL = "LEGAL"        # pháp lý / chính sách (MOCK)
    DOCUMENT = "DOCUMENT"  # hồ sơ / OCR (MOCK)


class ReportStatus(StrEnum):
    OK = "OK"            # specialist chạy trọn vẹn
    PARTIAL = "PARTIAL"  # thiếu dữ liệu / một phần lỗi, vẫn có kết quả dùng được
    FAILED = "FAILED"    # specialist lỗi hẳn (orchestrator vẫn compose phần còn lại)


class Claim(BaseModel):
    """Một luận điểm của specialist; mỗi luận điểm phải có nguồn (citation_ids)."""

    model_config = ConfigDict(extra="forbid")

    text: str
    citation_ids: tuple[str, ...] = ()
    # đánh dấu luận điểm suy luận không trực tiếp từ nguồn (compose sẽ hạ trọng số)
    is_inference: bool = False


class DomainReport(BaseModel):
    """Đầu ra chuẩn của MỖI specialist (Credit/Legal/Document).

    MOCK và REAL trả cùng schema này → cắm microservice thật không đổi Compose.
    """

    model_config = ConfigDict(extra="forbid")

    domain: Domain
    agent: str
    status: ReportStatus = ReportStatus.OK
    summary: str = ""
    claims: tuple[Claim, ...] = ()
    citations: tuple[Citation, ...] = ()
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    error: str | None = None

    @model_validator(mode="after")
    def _claims_cite_real_citations(self) -> "DomainReport":
        known = {c.id for c in self.citations}
        for claim in self.claims:
            for cid in claim.citation_ids:
                if cid not in known:
                    raise ValueError(
                        f"[{self.domain}] claim trích citation không tồn tại: {cid!r}"
                    )
        # Citation kiểu DOCUMENT bắt buộc có bbox để highlight được.
        for c in self.citations:
            if c.source_type == "DOCUMENT" and c.bbox is None:
                raise ValueError(f"citation DOCUMENT {c.id!r} thiếu bbox")
        return self


class ComposedClaim(BaseModel):
    """Luận điểm trong báo cáo tổng hợp; citation_ids trỏ về Citation gốc specialist."""

    model_config = ConfigDict(extra="forbid")

    text: str
    citation_ids: tuple[str, ...] = ()
    supported: bool = True  # False nếu verify không resolve được nguồn


class ComposedSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    domain: Domain | None = None
    claims: tuple[ComposedClaim, ...] = ()


class ComposedReport(BaseModel):
    """Báo cáo tổng hợp cho người duyệt — đã verify chống bịa nguồn."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: UUID
    question: str
    recommendation: str = ""
    sections: tuple[ComposedSection, ...] = ()
    # Citation gốc gộp từ mọi specialist (nguồn chân lý để UI resolve → highlight).
    citations: tuple[Citation, ...] = ()
    # Luận điểm bị loại nguồn ở bước verify (minh bạch, không giấu).
    unsupported_claims: tuple[str, ...] = ()
    domain_status: dict[str, ReportStatus] = Field(default_factory=dict)
    eval_rounds: int = 0
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _composed_claims_resolve(self) -> "ComposedReport":
        known = {c.id for c in self.citations}
        for section in self.sections:
            for claim in section.claims:
                for cid in claim.citation_ids:
                    if cid not in known:
                        raise ValueError(
                            f"composed claim trích citation không có trong nguồn gộp: {cid!r}"
                        )
                if claim.citation_ids and not claim.supported:
                    raise ValueError("claim có citation_ids thì không được supported=False")
        return self


def collect_citations(reports: list[DomainReport]) -> tuple[Citation, ...]:
    """Gộp toàn bộ Citation gốc từ các specialist (giữ thứ tự, khử trùng id)."""
    seen: set[str] = set()
    out: list[Citation] = []
    for report in reports:
        for c in report.citations:
            if c.id not in seen:
                seen.add(c.id)
                out.append(c)
    return tuple(out)
