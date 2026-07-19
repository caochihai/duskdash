"""Smoke test Engine (offline, dữ liệu THẬT-cấu-trúc từ 6 hồ sơ + OCR thật):

    PYTHONUTF8=1 PYTHONPATH=. python -m services.engine.smoke_test

Kiểm 3 rủi ro đã khoá + chạy deep-research trên hồ sơ thật.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from libs.contracts import AnalysisMode, AnalysisRequest, AuthorizedScope, Domain, ReportStatus

from .compose import verify_claim
from .data_client import ScopeViolation, SqlQuerySpec, build_scoped_sql
from .fixtures import casebook
from .orchestrator import run_deep_research

EMPLOYEE = casebook.customer_uuid("EMP-DEMO")
OUTSIDER = casebook.customer_uuid("CUST-OUTSIDER")


def _scope_for(case) -> AuthorizedScope:
    return AuthorizedScope(employee_id=EMPLOYEE, customer_ids=(case.customer_uuid,), loan_ids=())


def check_sql_scoping() -> None:
    case = casebook.by_case_id("CR-A01")
    scope = _scope_for(case)
    ok = SqlQuerySpec(metric="latest", table="banking.account_monthly_summary",
                      column="total_inflow", customer_id=case.customer_uuid)
    sql, _ = build_scoped_sql(ok, scope)
    assert "customer_id = ANY(%s)" in sql and "banking.account_monthly_summary" in sql

    for bad in (
        SqlQuerySpec(metric="latest", table="banking.account_monthly_summary",
                     column="total_inflow", customer_id=OUTSIDER),
        SqlQuerySpec(metric="sum", table="identity.employee", column="salary",
                     customer_id=case.customer_uuid),
        SqlQuerySpec(metric="sum", table="banking.account_monthly_summary", column="secret_col",
                     customer_id=case.customer_uuid),
    ):
        try:
            build_scoped_sql(bad, scope)
            raise AssertionError(f"phải chặn: {bad}")
        except ScopeViolation:
            pass
    print("[1] SQL scoping: OK (chặn customer ngoài scope + bảng/cột ngoài whitelist)")


def check_compose_verify() -> None:
    known = {"credit-1", "credit-2"}
    assert verify_claim(("credit-1",), known) == (("credit-1",), True)
    assert verify_claim(("ghost-9",), known) == ((), False)
    print("[2] Compose verify: OK (loại citation bịa, hạ cấp unsupported)")


async def _run_case(case_id: str) -> None:
    case = casebook.by_case_id(case_id)
    assert case, f"không có case {case_id}"
    req = AnalysisRequest(
        correlation_id=uuid4(),
        question=f"Đánh giá khả năng trả nợ và điều kiện phê duyệt cho {case.name}.",
        scope=_scope_for(case), mode=AnalysisMode.DEEP_RESEARCH,
        domains=(Domain.CREDIT, Domain.LEGAL, Domain.DOCUMENT),
        customer_id=case.customer_uuid, max_eval_rounds=1)
    resp = await run_deep_research(req)
    r = resp.report
    assert len(resp.domain_reports) == 3
    known = {c.id for c in r.citations}
    for sec in r.sections:
        for claim in sec.claims:
            for cid in claim.citation_ids:
                assert cid in known, f"citation không truy được: {cid}"
    doc_cits = [c for c in r.citations if c.source_type == "DOCUMENT"]
    has_ocr = case.ocr_slug and (casebook._OCR_DIR / f"{case.ocr_slug}.json").exists()
    if has_ocr:
        assert doc_cits and all(c.bbox is not None for c in doc_cits), "DOCUMENT citation phải có bbox"
    n_claims = sum(len(s.claims) for s in r.sections)
    print(f"    {case_id} {case.name[:34]:<34} [{case.decision_label:<18}] "
          f"{len(r.citations):>2} nguồn / {n_claims:>2} luận điểm / {len(doc_cits):>2} bbox / "
          f"unsupported={len(r.unsupported_claims)}")
    return r


async def check_deep_research() -> None:
    print("[3] Deep-research trên 6 hồ sơ THẬT:")
    for cid in ("CR-A01", "CR-B02", "CR-C03", "CR-I01", "CR-I02", "CR-I03"):
        await _run_case(cid)


async def check_scoping_runtime() -> None:
    # Nhân viên chỉ có scope KH khác → Credit/Document phải FAILED/PARTIAL (không lộ dữ liệu).
    a01 = casebook.by_case_id("CR-A01")
    b02 = casebook.by_case_id("CR-B02")
    wrong_scope = AuthorizedScope(employee_id=EMPLOYEE, customer_ids=(b02.customer_uuid,))
    req = AnalysisRequest(correlation_id=uuid4(), question="x", scope=wrong_scope,
                          customer_id=a01.customer_uuid, max_eval_rounds=0)
    resp = await run_deep_research(req)
    credit = next(d for d in resp.domain_reports if d.domain == Domain.CREDIT)
    assert credit.status == ReportStatus.FAILED, credit.status
    print("[4] Runtime scoping: OK (hỏi KH ngoài scope → Credit FAILED, không lộ số liệu)")


async def main() -> None:
    check_sql_scoping()
    check_compose_verify()
    await check_deep_research()
    await check_scoping_runtime()
    print("\nTẤT CẢ SMOKE TEST ENGINE: PASS")


if __name__ == "__main__":
    asyncio.run(main())
