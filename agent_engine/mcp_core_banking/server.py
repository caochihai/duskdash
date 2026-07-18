"""MCP server "core-banking": cổng duy nhất để agent chạm vào hệ thống nghiệp vụ.

Mọi tool call được ghi audit tại đây (tầng MCP = tầng kiểm soát tập trung).
Chạy: python -m mcp_core_banking.server
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from common import config  # noqa: E402

mcp = FastMCP("core-banking", host=config.HOST, port=config.MCP_CORE_BANKING_PORT)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.CORE_BANKING_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _audit(tool: str, args: dict) -> None:
    with _db() as db:
        db.execute(
            "INSERT INTO audit(ts, tool, args_json) VALUES (?,?,?)",
            (time.time(), tool, json.dumps(args, ensure_ascii=False, default=str)),
        )


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


@mcp.tool()
def get_business(business_id: str) -> dict:
    """Thông tin pháp nhân doanh nghiệp: ĐKKD, người đại diện, tài khoản."""
    _audit("get_business", {"business_id": business_id})
    with _db() as db:
        row = db.execute(
            "SELECT * FROM businesses WHERE business_id=?", (business_id,)
        ).fetchone()
    return dict(row) if row else {"error": f"không tìm thấy {business_id}"}


@mcp.tool()
def get_financials(business_id: str) -> list[dict]:
    """Số liệu tài chính các năm: doanh thu, EBITDA, nợ, dòng tiền về TK."""
    _audit("get_financials", {"business_id": business_id})
    with _db() as db:
        rows = db.execute(
            "SELECT * FROM financials WHERE business_id=? ORDER BY year", (business_id,)
        ).fetchall()
    return _rows(rows)


@mcp.tool()
def get_collateral(business_id: str) -> list[dict]:
    """Danh sách tài sản bảo đảm của doanh nghiệp kèm định giá và trạng thái pháp lý."""
    _audit("get_collateral", {"business_id": business_id})
    with _db() as db:
        rows = db.execute(
            "SELECT * FROM collateral WHERE business_id=?", (business_id,)
        ).fetchall()
    return _rows(rows)


@mcp.tool()
def check_blacklist(name: str, cccd: str = "") -> dict:
    """Tra cứu danh sách đen AML theo tên và/hoặc số CCCD."""
    _audit("check_blacklist", {"name": name, "cccd": "***"})
    with _db() as db:
        row = db.execute(
            "SELECT * FROM blacklist WHERE name=? OR (cccd<>'' AND cccd=?)",
            (name, cccd),
        ).fetchone()
    return {"hit": bool(row), "detail": dict(row) if row else None}


@mcp.tool()
def get_cic_status(business_id: str) -> dict:
    """Tra cứu CIC: nhóm nợ hiện tại và dư nợ quá hạn (dùng cho precondition check)."""
    _audit("get_cic_status", {"business_id": business_id})
    with _db() as db:
        row = db.execute("SELECT * FROM cic WHERE business_id=?", (business_id,)).fetchone()
    return dict(row) if row else {"business_id": business_id, "cic_group": 1, "overdue_amount": 0}


@mcp.tool()
def get_existing_loans(business_id: str) -> list[dict]:
    """Các khoản vay hiện hữu tại ngân hàng của doanh nghiệp."""
    _audit("get_existing_loans", {"business_id": business_id})
    with _db() as db:
        rows = db.execute(
            "SELECT * FROM loans WHERE business_id=?", (business_id,)
        ).fetchall()
    return _rows(rows)


@mcp.tool()
def create_loan_draft(case_id: str, business_id: str, amount: float, term_months: int) -> dict:
    """[DRY-RUN] Tạo bản nháp hồ sơ vay — không phát sinh hiệu lực nghiệp vụ."""
    _audit("create_loan_draft", {"case_id": case_id, "business_id": business_id, "amount": amount})
    draft_id = f"draft_{uuid.uuid4().hex[:10]}"
    with _db() as db:
        db.execute(
            "INSERT INTO loan_drafts VALUES (?,?,?,?,?,?,?)",
            (draft_id, case_id, business_id, amount, term_months, "draft", time.time()),
        )
    return {"draft_id": draft_id, "status": "draft"}


@mcp.tool()
def commit_loan(
    idempotency_key: str,
    case_id: str,
    business_id: str,
    amount: float,
    term_months: int,
    rate: float = 9.5,
) -> dict:
    """[COMMIT] Tạo khoản vay chính thức. Idempotent theo idempotency_key:
    gọi lại với cùng key trả về bản ghi đã có, không tạo trùng."""
    _audit("commit_loan", {"idempotency_key": idempotency_key, "case_id": case_id, "amount": amount})
    with _db() as db:
        existing = db.execute(
            "SELECT * FROM loans WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
        if existing:
            return {**dict(existing), "already_recorded": True}
        loan_id = f"LN{uuid.uuid4().hex[:8].upper()}"
        db.execute(
            "INSERT INTO loans VALUES (?,?,?,?,?,?,?,?,?)",
            (loan_id, idempotency_key, case_id, business_id, amount,
             term_months, rate, "active", time.time()),
        )
    return {"loan_id": loan_id, "status": "active", "already_recorded": False}


@mcp.tool()
def get_loan_by_idempotency(idempotency_key: str) -> dict:
    """[ĐỐI SOÁT] Tra khoản vay theo idempotency_key — dùng khi kết quả commit mơ hồ."""
    _audit("get_loan_by_idempotency", {"idempotency_key": idempotency_key})
    with _db() as db:
        row = db.execute(
            "SELECT * FROM loans WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
    return {"found": bool(row), "loan": dict(row) if row else None}


@mcp.tool()
def create_disbursement_schedule(loan_id: str, num_tranches: int = 2) -> dict:
    """Tạo lịch giải ngân chia đều theo số đợt."""
    _audit("create_disbursement_schedule", {"loan_id": loan_id, "num_tranches": num_tranches})
    with _db() as db:
        loan = db.execute("SELECT * FROM loans WHERE loan_id=?", (loan_id,)).fetchone()
        if not loan:
            return {"error": f"không tìm thấy khoản vay {loan_id}"}
        per = loan["amount"] / num_tranches
        for i in range(num_tranches):
            db.execute(
                "INSERT INTO disbursements(loan_id, tranche_no, amount, scheduled_date) "
                "VALUES (?,?,?,date('now', ?))",
                (loan_id, i + 1, per, f"+{i * 30} days"),
            )
    return {"loan_id": loan_id, "tranches": num_tranches, "amount_per_tranche": per}


@mcp.tool()
def get_audit_log(limit: int = 30) -> list[dict]:
    """Audit trail các tool call gần nhất tại tầng MCP."""
    with _db() as db:
        rows = db.execute(
            "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return _rows(rows)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
