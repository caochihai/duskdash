"""Seed mock core banking: 2 bộ hồ sơ SME demo + dữ liệu CIC/blacklist.

Chạy: python -m mcp_core_banking.seed  (từ thư mục backend)
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses(
  business_id TEXT PRIMARY KEY, name TEXT, tax_code TEXT, industry TEXT,
  industry_risk TEXT, established_year INTEGER, legal_rep_name TEXT,
  legal_rep_cccd TEXT, is_existing_customer INTEGER, account_number TEXT);
CREATE TABLE IF NOT EXISTS financials(
  business_id TEXT, year INTEGER, revenue REAL, ebitda REAL, total_debt REAL,
  equity REAL, current_assets REAL, current_liabilities REAL,
  debt_service REAL, bank_inflow REAL);
CREATE TABLE IF NOT EXISTS collateral(
  collateral_id TEXT PRIMARY KEY, business_id TEXT, type TEXT,
  description TEXT, valuation REAL, legal_status TEXT);
CREATE TABLE IF NOT EXISTS blacklist(name TEXT, cccd TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS cic(
  business_id TEXT PRIMARY KEY, cic_group INTEGER, overdue_amount REAL,
  note TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS loans(
  loan_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE, case_id TEXT,
  business_id TEXT, amount REAL, term_months INTEGER, rate REAL,
  status TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS loan_drafts(
  draft_id TEXT PRIMARY KEY, case_id TEXT, business_id TEXT, amount REAL,
  term_months INTEGER, status TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS disbursements(
  id INTEGER PRIMARY KEY AUTOINCREMENT, loan_id TEXT, tranche_no INTEGER,
  amount REAL, scheduled_date TEXT);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, tool TEXT, args_json TEXT);
"""


def main() -> None:
    db = sqlite3.connect(config.CORE_BANKING_DB)
    db.executescript(SCHEMA)
    db.execute("PRAGMA journal_mode=WAL")
    now = time.time()

    db.execute("DELETE FROM businesses"); db.execute("DELETE FROM financials")
    db.execute("DELETE FROM collateral"); db.execute("DELETE FROM blacklist")
    db.execute("DELETE FROM cic")

    # ---- B001: hồ sơ "sạch" — Công ty TNHH An Bình (có TSĐB) ----
    db.execute(
        "INSERT INTO businesses VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("B001", "Công ty TNHH An Bình", "0312345678", "Sản xuất bao bì",
         "normal", 2015, "Nguyễn Văn An", "079088001234", 1, "010203040506"),
    )
    db.execute("INSERT INTO financials VALUES (?,?,?,?,?,?,?,?,?,?)",
               ("B001", 2024, 20e9, 2.6e9, 3.0e9, 8.0e9, 6.5e9, 3.2e9, 1.8e9, 19.2e9))
    db.execute("INSERT INTO financials VALUES (?,?,?,?,?,?,?,?,?,?)",
               ("B001", 2025, 22e9, 2.9e9, 3.2e9, 8.8e9, 7.1e9, 3.4e9, 1.9e9, 21.0e9))
    db.execute(
        "INSERT INTO collateral VALUES (?,?,?,?,?,?)",
        ("C001", "B001", "real_estate",
         "Quyền sử dụng đất và nhà xưởng tại KCN Tân Bình, TP.HCM",
         6.0e9, "clear"),
    )
    db.execute("INSERT INTO cic VALUES (?,?,?,?,?)", ("B001", 1, 0, "Lịch sử tín dụng tốt", now))

    # ---- B002: hồ sơ "gài" — CTCP Xây dựng Trường Phát (tín chấp, nhiều cờ đỏ) ----
    db.execute(
        "INSERT INTO businesses VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("B002", "Công ty CP Xây dựng Trường Phát", "0387654321", "Xây dựng",
         "high", 2019, "Trần Quốc Bảo", "079090005678", 0, "060504030201"),
    )
    # DSCR = 1.5/1.6 < 1.2 ; bank_inflow 7.5 tỷ lệch xa doanh thu 18 tỷ trên BCTC
    db.execute("INSERT INTO financials VALUES (?,?,?,?,?,?,?,?,?,?)",
               ("B002", 2025, 18e9, 1.5e9, 6.5e9, 3.0e9, 4.0e9, 4.5e9, 1.6e9, 7.5e9))
    db.execute("INSERT INTO cic VALUES (?,?,?,?,?)",
               ("B002", 2, 350e6, "Từng phát sinh nợ nhóm 2 năm 2025", now))

    # ---- Blacklist mẫu (dùng cho benchmark, không trùng 2 hồ sơ demo) ----
    db.execute("INSERT INTO blacklist VALUES (?,?,?)",
               ("Lê Hoàng Cường", "079075009999", "Liên quan vụ án lừa đảo tín dụng 2024"))

    db.commit()
    db.close()
    print(f"Seeded {config.CORE_BANKING_DB}")


if __name__ == "__main__":
    main()
