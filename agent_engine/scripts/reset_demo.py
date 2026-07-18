"""Reset 1 chạm về trạng thái demo sạch (chạy giữa 2 lượt demo).

Chạy: python -m scripts.reset_demo   (KHÔNG cần restart các service)
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3  # noqa: E402

from common import config  # noqa: E402
from mcp_core_banking import seed  # noqa: E402

# Core banking: seed lại toàn bộ + xóa loans/drafts/disbursements/audit
seed.main()
db = sqlite3.connect(config.CORE_BANKING_DB)
for table in ("loans", "loan_drafts", "disbursements", "audit"):
    db.execute(f"DELETE FROM {table}")
db.commit()

# Gateway: xóa cases/events/plans/tokens
if config.GATEWAY_DB.exists():
    g = sqlite3.connect(config.GATEWAY_DB)
    for table in ("cases", "events", "plans", "tokens"):
        try:
            g.execute(f"DELETE FROM {table}")
        except sqlite3.OperationalError:
            pass
    g.commit()

print("Đã reset toàn bộ dữ liệu demo (core banking + gateway).")
