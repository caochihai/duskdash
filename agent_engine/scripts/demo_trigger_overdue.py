"""Twist demo #3: mock phát sinh nợ quá hạn cho B001 SAU khi phê duyệt.

Chạy giữa lúc bấm Approve và lúc commit (hoặc trước approve để chặn ngay):
    python -m scripts.demo_trigger_overdue          # bật nợ quá hạn
    python -m scripts.demo_trigger_overdue --reset  # trả về sạch
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config  # noqa: E402

db = sqlite3.connect(config.CORE_BANKING_DB)
if "--reset" in sys.argv:
    db.execute("UPDATE cic SET cic_group=1, overdue_amount=0, "
               "note='Lịch sử tín dụng tốt', updated_at=? WHERE business_id='B001'",
               (time.time(),))
    db.commit()
    print("B001: CIC đã trả về trạng thái sạch")
else:
    db.execute("UPDATE cic SET cic_group=2, overdue_amount=420000000, "
               "note='Phát sinh nợ quá hạn tại TCTD khác (cập nhật CIC mới nhất)', "
               "updated_at=? WHERE business_id='B001'", (time.time(),))
    db.commit()
    print("B001: đã mock PHÁT SINH NỢ QUÁ HẠN 420,000,000 VND sau phê duyệt")
