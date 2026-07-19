"""Nền chung cho specialist: chữ ký chạy + tiện ích dựng citation có nguồn thật."""

from __future__ import annotations

from typing import Protocol

from libs.contracts import AnalysisRequest, Domain, DomainReport

from ..data_client import DataClient


class Specialist(Protocol):
    domain: Domain
    name: str

    async def run(self, request: AnalysisRequest, data: DataClient) -> DomainReport: ...


def cid(domain: Domain, n: int) -> str:
    """Id citation ổn định trong phạm vi một báo cáo (dễ verify ở Compose)."""
    return f"{domain.value.lower()}-{n}"
