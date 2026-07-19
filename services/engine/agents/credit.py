"""Credit Agent (REAL, +SQL tool có rào chắn) → báo cáo tài chính có nguồn.

Xử lý cả doanh nghiệp (chỉ số thanh khoản/đòn bẩy) lẫn cá nhân (DTI/thu nhập). Mọi
con số dẫn về một Citation RECORD (bản ghi) hoặc SQL (truy vấn đã ép scope). LLM chỉ
viết summary từ các claim đã có nguồn.
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
from ..data_client import CreditFacts, DataClient, ScopeViolation, SqlQuerySpec
from .base import cid


def _vnd(x: float) -> str:
    return f"{x:,.0f} đ".replace(",", ".")


def _bn(x: float) -> str:
    return f"{x / 1e9:.1f} tỷ".replace(".", ",")


class CreditAgent:
    domain = Domain.CREDIT
    name = "credit-agent"

    async def run(self, request: AnalysisRequest, data: DataClient) -> DomainReport:
        if request.customer_id is None:
            return DomainReport(domain=self.domain, agent=self.name,
                                status=ReportStatus.PARTIAL,
                                summary="Thiếu customer_id — không phân tích tài chính được.")
        try:
            f = await data.get_credit_facts(request.customer_id, request.scope)
        except ScopeViolation as e:
            return DomainReport(domain=self.domain, agent=self.name,
                                status=ReportStatus.FAILED, error=str(e),
                                summary="Truy cập dữ liệu tài chính bị chặn bởi scope.")

        citations: list[Citation] = []
        claims: list[Claim] = []
        n = 0

        def add(quote: str, text: str, source=SourceType.RECORD, **kw) -> None:
            nonlocal n
            n += 1
            c = cid(self.domain, n)
            citations.append(Citation(id=c, source_type=source, quote=quote,
                                      record_id=f.customer_id, **kw))
            claims.append(Claim(text=text, citation_ids=(c,)))

        # --- Hạn mức đề nghị vs khuyến nghị ---
        add(f"Đề nghị cấp: {_bn(f.requested_limit)}; hệ thống khuyến nghị: {_bn(f.recommended_limit)}",
            f"Khách đề nghị hạn mức {_bn(f.requested_limit)}; mức khuyến nghị theo hồ sơ là "
            f"{_bn(f.recommended_limit)}"
            + ("." if f.recommended_limit >= f.requested_limit
               else f" (thu hẹp {100 - f.recommended_limit * 100 // max(f.requested_limit,1)}%)."))

        # --- Doanh nghiệp: chỉ số tài chính ---
        if f.metrics:
            m = f.metrics
            cr, dte = m.get("current_ratio"), m.get("debt_to_equity")
            if cr is not None:
                add(f"Current ratio = {cr}; quick ratio = {m.get('quick_ratio')}",
                    f"Thanh khoản: current ratio {cr} "
                    f"({'lành mạnh' if cr >= 1.2 else 'yếu, dưới 1.2'}).")
            if dte is not None:
                add(f"Debt/Equity = {dte}",
                    f"Đòn bẩy D/E {dte} ({'ở mức an toàn' if dte <= 1 else 'cao'}).")
            add(f"DSO = {m.get('dso_days')} ngày; DIO = {m.get('dio_days')} ngày",
                f"Vòng quay: DSO {m.get('dso_days')} ngày, DIO {m.get('dio_days')} ngày.")

        # --- Cá nhân: thu nhập & DTI ---
        if f.income:
            inc = f.income
            dti = inc.get("dti")
            verified = inc.get("verified_monthly_vnd") or inc.get("verified_household_monthly_vnd")
            add(f"Thu nhập xác minh: {_vnd(verified or 0)}/tháng; "
                f"nợ hiện hữu: {_vnd(inc.get('existing_debt_monthly_vnd') or 0)}/tháng; "
                f"nghĩa vụ mới: {_vnd(inc.get('new_payment_monthly_vnd') or 0)}/tháng",
                f"DTI = {dti} ({'trong ngưỡng' if (dti or 9) <= 0.5 else 'vượt ngưỡng 0.5'}), "
                f"thu nhập xác minh {_vnd(verified or 0)}/tháng.")

        # --- Sức khoẻ dòng tiền (chung) ---
        a = f.annual
        add(f"Dòng tiền năm: vào {_bn(a.get('inflow',0))}, ra {_bn(a.get('outflow',0))}, "
            f"số dư TB {_bn(a.get('avg_balance',0))}, thấp nhất {_bn(a.get('min_balance',0))}; "
            f"quá hạn {a.get('overdraft_days',0)} ngày, hoàn trả {a.get('returned',0)} lần",
            f"Dòng tiền: vào {_bn(a.get('inflow',0))}/năm, số dư thấp nhất "
            f"{_bn(a.get('min_balance',0))}, {a.get('overdraft_days',0)} ngày âm quỹ, "
            f"{a.get('returned',0)} giao dịch bị hoàn.")
        if a.get("gambling") or a.get("crypto"):
            add(f"Giao dịch cờ bạc {_bn(a.get('gambling',0))}, crypto {_bn(a.get('crypto',0))}",
                f"CẢNH BÁO dòng tiền rủi ro: cờ bạc {_bn(a.get('gambling',0))}, "
                f"crypto {_bn(a.get('crypto',0))}.")

        # --- Rủi ro ---
        add(f"Risk grade {f.risk_grade}, PD 12m {f.pd_12m:.1%}, quyết định hệ thống: {f.decision_label}",
            f"Xếp hạng {f.risk_grade}, xác suất vỡ nợ 12 tháng {f.pd_12m:.1%}.")

        # --- SQL tool (đã ép scope + whitelist) ---
        try:
            spec = SqlQuerySpec(metric="latest", table="banking.account_monthly_summary",
                                column="total_inflow", customer_id=request.customer_id)
            res = await data.run_sql(spec, request.scope)
            n += 1
            c = cid(self.domain, n)
            citations.append(Citation(id=c, source_type=SourceType.SQL,
                                      quote=f"Dòng tiền vào tháng gần nhất: {_vnd(res.value)} "
                                            f"(query {res.query_id}, {res.row_count} kỳ)",
                                      sql_query_id=res.query_id))
            claims.append(Claim(text=f"Dòng tiền vào tháng gần nhất đạt {_bn(res.value)}.",
                                citation_ids=(c,)))
        except ScopeViolation:
            pass

        summary = await llm.narrate(
            system="Bạn là chuyên viên phân tích tín dụng SHB. Viết 2-3 câu súc tích, "
                   "chỉ dựa trên các gạch đầu dòng, không thêm số liệu mới.",
            user=f"Phân tích tài chính {f.name} ({f.customer_type}):\n"
                 + "\n".join(f"- {c.text}" for c in claims))

        status = (ReportStatus.OK if f.decision_label == "APPROVE"
                  else ReportStatus.PARTIAL)  # CONDITIONAL/REJECT: có cảnh báo, cần điều kiện
        return DomainReport(domain=self.domain, agent=self.name, status=status,
                            summary=summary, claims=tuple(claims),
                            citations=tuple(citations), confidence=0.85)
