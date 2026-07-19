"""Orchestrator deep-research — fan-out song song 3 specialist → Compose + eval.

- Fan-out bằng asyncio.gather; một specialist lỗi KHÔNG làm sập cả cụm
  (trả DomainReport FAILED, Compose vẫn tổng hợp phần còn lại).
- Eval/feedback loop có giới hạn vòng: phát hiện luận điểm không nguồn / mâu thuẫn
  chéo → ghi nhận, chốt sau max_eval_rounds (đúng ý thiết kế gốc, tránh loop vô hạn).
"""

from __future__ import annotations

import asyncio

from libs.contracts import (
    AnalysisRequest,
    AnalysisResponse,
    Domain,
    DomainReport,
    ReportStatus,
)

from . import compose
from .agents.credit import CreditAgent
from .agents.document import DocumentAgent
from .agents.legal import LegalAgent
from .data_client import DataClient, get_data_client

_REGISTRY = {
    Domain.CREDIT: CreditAgent(),
    Domain.LEGAL: LegalAgent(),
    Domain.DOCUMENT: DocumentAgent(),
}


async def _run_one(domain: Domain, request: AnalysisRequest, data: DataClient) -> DomainReport:
    agent = _REGISTRY[domain]
    try:
        return await asyncio.wait_for(agent.run(request, data), timeout=45)
    except Exception as e:  # noqa: BLE001 - cô lập lỗi từng specialist
        return DomainReport(domain=domain, agent=getattr(agent, "name", domain.value),
                            status=ReportStatus.FAILED, error=str(e),
                            summary=f"Specialist {domain.value} lỗi khi chạy.")


def _eval(reports: list[DomainReport]) -> list[str]:
    """Trả danh sách vấn đề cần feedback (rỗng = đạt)."""
    issues: list[str] = []
    for r in reports:
        for claim in r.claims:
            if not claim.citation_ids and not claim.is_inference:
                issues.append(f"[{r.domain.value}] luận điểm thiếu nguồn: {claim.text[:60]}")
    return issues


async def run_deep_research(request: AnalysisRequest) -> AnalysisResponse:
    data = get_data_client()
    trace: list[str] = []
    domains = list(request.domains)
    trace.append(f"fan-out song song: {', '.join(d.value for d in domains)}")

    reports = list(await asyncio.gather(*(_run_one(d, request, data) for d in domains)))

    rounds = 0
    while rounds < request.max_eval_rounds:
        issues = _eval(reports)
        if not issues:
            break
        rounds += 1
        trace.append(f"eval vòng {rounds}: {len(issues)} vấn đề → chạy lại specialist liên quan")
        bad = {d for d in domains
               for r in reports if r.domain == d and any(d.value in i for i in issues)}
        if not bad:
            break
        refreshed = await asyncio.gather(*(_run_one(d, request, data) for d in bad))
        by_domain = {r.domain: r for r in reports}
        for r in refreshed:
            by_domain[r.domain] = r
        reports = [by_domain[d] for d in domains]

    report = await compose.compose(request.correlation_id, request.question, reports)
    report = report.model_copy(update={"eval_rounds": rounds})
    trace.append(f"compose xong: {len(report.citations)} nguồn, "
                 f"{len(report.unsupported_claims)} luận điểm bị loại nguồn")
    return AnalysisResponse(
        correlation_id=request.correlation_id, report=report,
        domain_reports=tuple(reports), trace=tuple(trace))
