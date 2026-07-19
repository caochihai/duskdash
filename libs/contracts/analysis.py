"""Hợp đồng giữa Platform (Máy 1) và Deep-Research Engine (Máy 2).

- `AuthorizedScope`: quyền dữ liệu nhân viên → Engine bị ÉP truy vấn trong scope này.
- `AnalysisRequest/Response`: Platform giao việc cho Engine, nhận báo cáo có nguồn.
- `AgentRoute`: 5 mức của Agent User (auth-first, xem docs/redesign/PLAN.md §2).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from libs.contracts._enum import StrEnum
from libs.contracts.report import ComposedReport, Domain, DomainReport


class AgentRoute(StrEnum):
    """5 mức phân loại của Agent User (Platform). Auth luôn đi trước phân loại."""

    REFUSE = "REFUSE"                # mức 1: lệch chủ đề
    NEEDS_CONTEXT = "NEEDS_CONTEXT"  # mức 2: đúng chủ đề, thiếu ngữ cảnh
    DIRECT = "DIRECT"                # mức 3: trả lời ngay + citation (FAQ/định nghĩa)
    SINGLE_AGENT = "SINGLE_AGENT"    # mức 4: đủ ngữ cảnh, 1 lĩnh vực
    DEEP_RESEARCH = "DEEP_RESEARCH"  # mức 5: phức tạp, đa lĩnh vực


class AnalysisMode(StrEnum):
    SINGLE_AGENT = "SINGLE_AGENT"    # chạy 1 specialist
    DEEP_RESEARCH = "DEEP_RESEARCH"  # fan-out 3 specialist + compose


class AuthorizedScope(BaseModel):
    """Ranh giới dữ liệu Platform cấp cho một request Engine.

    Mọi truy vấn Credit+SQL bị ép `WHERE customer_id IN customer_ids`. Engine
    KHÔNG được truy cập ngoài scope này (rủi ro #1 — SQL scoping).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    employee_id: UUID
    customer_ids: tuple[UUID, ...] = ()
    loan_ids: tuple[UUID, ...] = ()

    def allows_customer(self, customer_id: UUID) -> bool:
        return customer_id in self.customer_ids

    def allows_loan(self, loan_id: UUID) -> bool:
        return loan_id in self.loan_ids


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: UUID
    question: str
    scope: AuthorizedScope
    mode: AnalysisMode = AnalysisMode.DEEP_RESEARCH
    # specialist cần chạy (mode SINGLE_AGENT thường 1 phần tử)
    domains: tuple[Domain, ...] = (Domain.CREDIT, Domain.LEGAL, Domain.DOCUMENT)
    customer_id: UUID | None = None
    loan_id: UUID | None = None
    document_ids: tuple[UUID, ...] = ()
    max_eval_rounds: int = Field(default=1, ge=0, le=3)


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: UUID
    report: ComposedReport
    domain_reports: tuple[DomainReport, ...] = ()
    trace: tuple[str, ...] = ()
