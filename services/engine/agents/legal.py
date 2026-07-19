"""Legal Agent (MOCK, contract-compatible) → báo cáo pháp lý có nguồn.

Mock đọc fixture chính sách nhưng TRẢ ĐÚNG DomainReport schema microservice thật
sẽ trả (citation POLICY: policy_clause_id + quote). Cắm service thật không đổi Compose.
"""

from __future__ import annotations

from libs.contracts import (
    AnalysisRequest,
    Citation,
    Claim,
    Domain,
    DomainReport,
    ReportStatus,
    SourceType,
)

from .. import llm
from ..data_client import DataClient
from .base import cid

# Fixture điều khoản chính sách (đúng hình dạng RAG chính sách thật).
_POLICY = [
    ("CREDIT-POLICY-3.2", "DSCR tối thiểu cho vay bổ sung vốn lưu động là 1.25."),
    ("CREDIT-POLICY-4.1", "Tỷ lệ cho vay trên TSBĐ (LTV) không vượt 80% với BĐS."),
    ("AML-POLICY-2.4", "Bắt buộc sàng lọc AML/PEP và lưu hồ sơ KYC trước giải ngân."),
]


class LegalAgent:
    domain = Domain.LEGAL
    name = "legal-agent"

    async def run(self, request: AnalysisRequest, data: DataClient) -> DomainReport:
        citations: list[Citation] = []
        claims: list[Claim] = []
        for i, (clause_id, text) in enumerate(_POLICY, start=1):
            c = cid(self.domain, i)
            citations.append(Citation(
                id=c, source_type=SourceType.POLICY, quote=text,
                policy_clause_id=clause_id))
            claims.append(Claim(
                text=f"Điều khoản {clause_id} áp dụng: {text}",
                citation_ids=(c,)))
        claims.append(Claim(
            text="Hồ sơ cần hoàn tất sàng lọc AML/PEP trước khi trình phê duyệt.",
            citation_ids=(cid(self.domain, 3),)))

        summary = await llm.narrate(
            system="Bạn là chuyên viên pháp chế ngân hàng. Tóm tắt tuân thủ trong 2-3 câu, "
                   "chỉ dựa trên các điều khoản liệt kê.",
            user="Rà soát pháp lý khoản vay:\n" + "\n".join(f"- {c.text}" for c in claims),
        )
        return DomainReport(
            domain=self.domain, agent=self.name, status=ReportStatus.OK,
            summary=summary, claims=tuple(claims), citations=tuple(citations),
            confidence=0.8)
