"""Cổng dữ liệu khách cho Engine — MỌI truy vấn bị ép theo AuthorizedScope.

Rủi ro #1 (SQL scoping) khoá ở đây, KHÔNG ở prompt:
- Specialist không ghép SQL tự do. Nó phát `SqlQuerySpec` có cấu trúc; `build_scoped_sql`
  compile ra SQL chỉ-đọc, parametrized, ÉP `customer_id = ANY(scope)` + whitelist bảng/cột.
- Truy vấn ngoài scope → raise ScopeViolation.

DATA_PROVIDER=mock → dữ liệu THẬT-cấu-trúc từ 6 hồ sơ (services/engine/fixtures/casebook),
OCR THẬT (bbox). Engine chạy standalone không cần Platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from libs.contracts import AuthorizedScope

from . import config

# Bảng/cột được phép cho SQL tool (whitelist cứng — LLM không mở rộng được).
# Tên bảng/cột KHỚP schema infra thật (infra/database/migrations/V005). Bảng keyed
# theo account_id → row-level scope ép qua JOIN banking.account.customer_id.
_ALLOWED_TABLES: dict[str, set[str]] = {
    "banking.account_monthly_summary": {
        "total_inflow", "total_outflow", "salary_inflow", "loan_payment",
        "cash_deposit", "average_balance", "minimum_balance", "transaction_count",
    },
}
_ALLOWED_METRICS = {"sum", "count", "avg", "latest"}

# Map cột infra → field trong dataset mock (mock dùng tên khác vài chỗ).
_MOCK_COL = {"average_balance": "average_balance", "minimum_balance": "minimum_balance"}


class ScopeViolation(PermissionError):
    """Truy vấn vượt quyền dữ liệu nhân viên."""


@dataclass(frozen=True)
class SqlQuerySpec:
    metric: str                 # sum | count | avg | latest
    table: str                  # phải nằm trong _ALLOWED_TABLES
    column: str | None = None
    customer_id: UUID | None = None
    period: str | None = None   # "YYYY-MM"; None = tháng gần nhất (year_month)


@dataclass(frozen=True)
class SqlResult:
    query_id: str
    sql: str
    value: float
    row_count: int


def build_scoped_sql(spec: SqlQuerySpec, scope: AuthorizedScope) -> tuple[str, list[Any]]:
    """Compile spec → (SQL parametrized, params). Ném lỗi nếu vi phạm whitelist/scope."""
    if spec.metric not in _ALLOWED_METRICS:
        raise ScopeViolation(f"metric không cho phép: {spec.metric!r}")
    cols = _ALLOWED_TABLES.get(spec.table)
    if cols is None:
        raise ScopeViolation(f"bảng không nằm trong whitelist: {spec.table!r}")
    if spec.metric in ("sum", "avg", "latest"):
        if spec.column not in cols:
            raise ScopeViolation(f"cột không cho phép: {spec.column!r}")
        agg = f"s.{spec.column}" if spec.metric == "latest" else f"{spec.metric.upper()}(s.{spec.column})"
    else:
        agg = "COUNT(*)"

    if spec.customer_id is None or not scope.allows_customer(spec.customer_id):
        raise ScopeViolation("customer_id nằm ngoài authorized_scope")

    # Row-level scope ép qua JOIN account: bảng summary keyed theo account_id,
    # chủ tài khoản phải nằm trong authorized_scope (2 lớp: whitelist + scope + KH cụ thể).
    where = ["a.customer_id = ANY(%s)", "a.customer_id = %s"]
    params: list[Any] = [[str(c) for c in scope.customer_ids], str(spec.customer_id)]
    if spec.period:
        where.append("s.year_month = %s")
        params.append(spec.period)
    order = " ORDER BY s.year_month DESC LIMIT 1" if spec.metric == "latest" else ""
    sql = (f"SELECT {agg} FROM {spec.table} s "
           f"JOIN banking.account a ON a.id = s.account_id WHERE "
           + " AND ".join(where) + order)
    return sql, params


@dataclass(frozen=True)
class CreditFacts:
    """Dữ kiện tài chính chuẩn cho Credit agent (provider-agnostic)."""

    customer_id: UUID
    name: str
    customer_type: str          # CORPORATE | INDIVIDUAL
    risk_grade: str
    pd_12m: float
    decision_label: str
    kyc_status: str
    aml_status: str
    fraud_risk: str
    pep_flag: bool
    requested_limit: int
    recommended_limit: int
    metrics: dict | None        # doanh nghiệp: current_ratio, debt_to_equity, dso, dio...
    income: dict | None         # cá nhân: verified_monthly, existing_debt_monthly, dti...
    annual: dict                # inflow/outflow/avg_balance/min_balance/overdraft/returned...


@dataclass(frozen=True)
class DocLine:
    document_id: UUID
    page: int
    text: str
    bbox: dict[str, Any]
    confidence: float


class DataClient(Protocol):
    async def get_credit_facts(self, customer_id: UUID, scope: AuthorizedScope) -> CreditFacts: ...
    async def run_sql(self, spec: SqlQuerySpec, scope: AuthorizedScope) -> SqlResult: ...
    async def get_document_lines(self, customer_id: UUID, scope: AuthorizedScope,
                                 limit: int = 6) -> list[DocLine]: ...


# --------------------------------------------------------------------------- #
# Mock provider — dữ liệu THẬT-cấu-trúc từ 6 hồ sơ + OCR thật.
# --------------------------------------------------------------------------- #

class MockDataClient:
    async def get_credit_facts(self, customer_id: UUID, scope: AuthorizedScope) -> CreditFacts:
        from .fixtures import casebook  # noqa: PLC0415 - tránh vòng import

        if not scope.allows_customer(customer_id):
            raise ScopeViolation("customer ngoài scope")
        c = casebook.get_case(customer_id)
        if c is None:
            raise ScopeViolation(f"không có hồ sơ cho customer {customer_id}")
        return CreditFacts(
            customer_id=customer_id, name=c.name, customer_type=c.customer_type,
            risk_grade=c.risk_grade, pd_12m=c.pd_12m, decision_label=c.decision_label,
            kyc_status=c.kyc_status, aml_status=c.aml_status, fraud_risk=c.fraud_risk,
            pep_flag=c.pep_flag, requested_limit=c.requested_limit,
            recommended_limit=c.recommended_limit, metrics=c.metrics, income=c.income,
            annual=c.annual)

    async def run_sql(self, spec: SqlQuerySpec, scope: AuthorizedScope) -> SqlResult:
        from .fixtures import casebook  # noqa: PLC0415

        sql, _params = build_scoped_sql(spec, scope)  # ép scope + whitelist TRƯỚC
        c = casebook.get_case(spec.customer_id) if spec.customer_id else None
        months = c.months if c else []
        if spec.period:
            months = [m for m in months if m.get("period") == spec.period]
        if spec.metric == "count":
            value = float(sum(m.get("transaction_count", 0) for m in months))
        elif spec.metric == "latest":
            value = float(months[-1].get(spec.column, 0)) if months else 0.0
        elif spec.metric == "avg":
            vals = [float(m.get(spec.column, 0)) for m in months]
            value = sum(vals) / len(vals) if vals else 0.0
        else:  # sum
            value = float(sum(m.get(spec.column, 0) for m in months))
        return SqlResult(query_id=f"q_{abs(hash(sql)) % 10**8:08d}", sql=sql,
                         value=value, row_count=len(months))

    async def get_document_lines(self, customer_id: UUID, scope: AuthorizedScope,
                                 limit: int = 6) -> list[DocLine]:
        from .fixtures import casebook  # noqa: PLC0415

        if not scope.allows_customer(customer_id):
            raise ScopeViolation("customer ngoài scope")
        c = casebook.get_case(customer_id)
        if c is None:
            return []
        return [DocLine(document_id=ln.document_id, page=ln.page, text=ln.text,
                        bbox=ln.bbox, confidence=ln.confidence)
                for ln in c.document_lines(limit=limit)]


def get_data_client() -> DataClient:
    if config.DATA_PROVIDER == "mock":
        return MockDataClient()
    from .platform_data_client import HttpDataClient  # noqa: PLC0415 - optional dep

    return HttpDataClient(config.PLATFORM_DATA_URL, config.PLATFORM_SERVICE_TOKEN)
