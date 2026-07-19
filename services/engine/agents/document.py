"""Document Agent (MOCK contract, OCR THẬT) → báo cáo hồ sơ có nguồn (bbox).

Đọc dòng OCR THẬT (Azure prebuilt-read, có bbox) của bộ hồ sơ khách qua Data API,
đối chiếu hồ sơ. Citation kiểu DOCUMENT mang bbox — nguồn cho highlight kiểu NotebookLM.
"""

from __future__ import annotations

from libs.contracts import (
    AnalysisRequest,
    BBox,
    Citation,
    Claim,
    Domain,
    DomainReport,
    ReportStatus,
    SourceType,
)

from ..data_client import DataClient, ScopeViolation
from .base import cid


class DocumentAgent:
    domain = Domain.DOCUMENT
    name = "document-agent"

    async def run(self, request: AnalysisRequest, data: DataClient) -> DomainReport:
        if request.customer_id is None:
            return DomainReport(domain=self.domain, agent=self.name,
                                status=ReportStatus.PARTIAL,
                                summary="Thiếu customer_id — chưa có tài liệu để đối chiếu.")
        try:
            lines = await data.get_document_lines(request.customer_id, request.scope, limit=6)
        except ScopeViolation as e:
            return DomainReport(domain=self.domain, agent=self.name,
                                status=ReportStatus.FAILED, error=str(e),
                                summary="Truy cập tài liệu bị chặn bởi scope.")
        if not lines:
            return DomainReport(domain=self.domain, agent=self.name,
                                status=ReportStatus.PARTIAL,
                                summary="Chưa có kết quả OCR cho hồ sơ này "
                                        "(chạy build_ocr_fixtures để nạp).")

        citations: list[Citation] = []
        for i, ln in enumerate(lines, start=1):
            c = cid(self.domain, i)
            citations.append(Citation(
                id=c, source_type=SourceType.DOCUMENT, quote=ln.text,
                document_id=ln.document_id, bbox=BBox(**ln.bbox),
                confidence=ln.confidence))

        claims = [Claim(
            text="Đã đọc được các trường định danh hồ sơ (OCR Azure) và trích dẫn đúng vị trí "
                 "trên tài liệu gốc để đối chiếu.",
            citation_ids=tuple(c.id for c in citations))]
        avg_conf = sum(c.confidence or 0 for c in citations) / len(citations)
        summary = (f"Hồ sơ hiện diện và đọc được (độ tin cậy OCR trung bình {avg_conf:.0%}); "
                   f"trích xuất {len(citations)} dòng có toạ độ để highlight và đối chiếu.")
        return DomainReport(domain=self.domain, agent=self.name, status=ReportStatus.OK,
                            summary=summary, claims=tuple(claims),
                            citations=tuple(citations), confidence=0.8)
