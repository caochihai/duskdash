"""Full luồng hồ sơ thật: Trần Quốc Bảo vay 5 tỷ / 60 tháng — 10 ảnh chụp hồ sơ.

Đo thời gian từng stage từ event stream. Chạy: python -m scripts.demo_tran_quoc_bao
(cần run_all.py đang chạy, LLM_MODE=hybrid)
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from common import config  # noqa: E402

G = config.GATEWAY_URL
DOCS_DIR = Path(__file__).resolve().parent.parent / "tran_quoc_bao_test"

# Ánh xạ 10 ảnh -> doc_type (sao kê dùng schema riêng để code tính dòng tiền)
FILES = [
    ("phieu_nghiep_vu", "z8055567560782_fece84e38852cf6556c59c72b32049fb.jpg"),  # kết luận thẩm định
    ("phieu_nghiep_vu", "z8055567647116_ed972edc43ae7fd4d8df06b63898d612.jpg"),  # phiếu KYC
    ("phieu_nghiep_vu", "z8055567720319_2d5f4f41a8182951bff78c501ba5ea69.jpg"),  # HĐLĐ
    ("sao_ke", "z8055567765952_cf775243260f1abc14af6d88db5005f2.jpg"),           # sao kê 12T
    ("phieu_nghiep_vu", "z8055567808405_41f062f64ccd1724e11ea775d6292a06.jpg"),  # báo cáo CIC
    ("phieu_nghiep_vu", "z8055567896565_8a44b9fb58620a3ded32d4f3b1462fb6.jpg"),  # đơn đề nghị vay
    ("phieu_nghiep_vu", "z8055567974302_9fbe71f842f120fc93d41b489d67f28d.jpg"),  # HĐ đặt cọc
    ("phieu_nghiep_vu", "z8055568045918_409570a299084483759bbf07d9255dae.jpg"),  # thẩm định giá
    ("phieu_nghiep_vu", "z8055568133905_75928bc088409ad51f6a82dd5a38fa8b.jpg"),  # nghĩa vụ nợ
    ("phieu_nghiep_vu", "z8055568221574_2a6be5c19f803e1f35f8627581a992fb.jpg"),  # phiếu AML
]

CASE = {
    "request": {
        # Trần Quốc Bảo là đại diện pháp luật của B002 trong mock core banking.
        # (Giới hạn hiện tại: hệ thống là luồng SME — xem đánh giá cuối.)
        "business_id": "B002",
        "amount": 5_000_000_000,
        "term_months": 60,
        "purpose": "Vay mua nhà ở; lãi suất đề nghị 6%/năm, kỳ trả lãi 2 lần/năm",
        "has_collateral": True,  # khách khai thế chấp căn hộ dự kiến mua
    },
    "submitted_by": "khach_hang_tran_quoc_bao",
    "documents": [
        {"doc_type": t, "image_path": str(DOCS_DIR / f)} for t, f in FILES
    ],
}


async def main() -> None:
    t_start = time.perf_counter()
    async with httpx.AsyncClient(timeout=60) as client:
        r = (await client.post(f"{G}/cases", json=CASE)).json()
        case_id = r["case_id"]
        print(f"Case: {case_id} — Trần Quốc Bảo, vay 5,000,000,000 VND / 60 tháng")
        print(f"Hồ sơ đính kèm: {len(CASE['documents'])} ảnh chụp\n")

        await client.post(f"{G}/cases/{case_id}/run")
        final_states = {"Pending Approval", "Needs Info", "Rejected", "Escalated"}
        state = None
        for _ in range(600):
            case = (await client.get(f"{G}/cases/{case_id}")).json()
            state = case.get("state")
            if state in final_states:
                break
            await asyncio.sleep(1)
        wall = time.perf_counter() - t_start

        events = (await client.get(f"{G}/cases/{case_id}/events")).json()

        # ---- phân tích thời gian từng stage từ events ----
        t0 = events[0]["ts"]
        starts, ends = {}, {}
        for e in events:
            if e["type"] == "task_started":
                starts[(e["agent"], e["payload"].get("task_id"))] = e["ts"]
            elif e["type"] == "task_finished":
                ends[(e["agent"], e["payload"].get("task_id"))] = e["ts"]
        plan_ev = next((e for e in events if e["type"] == "plan_created"), None)

        print("===== THỜI GIAN TỪNG STAGE =====")
        if plan_ev:
            print(f"  Planner (LLM sinh DAG):      {plan_ev['ts'] - t0:6.1f}s "
                  f"(source: {plan_ev['payload'].get('source')})")
        for (agent, tid), ts in sorted(starts.items(), key=lambda x: x[1]):
            if (agent, tid) in ends:
                dur = ends[(agent, tid)] - ts
                print(f"  {agent:<12} {str(tid):<14} chạy: {dur:6.1f}s")
        print(f"  TỔNG luồng (wall-clock):     {wall:6.1f}s -> trạng thái: {state}")

        # ---- verdicts & findings ----
        print("\n===== KẾT QUẢ TỪNG CHUYÊN GIA =====")
        for e in events:
            if e["type"] == "task_finished":
                v = e["payload"].get("verdict", {})
                print(f"\n[{e['agent'].upper()}] {v.get('decision', '?').upper()}: "
                      f"{v.get('summary', '')[:200]}")
                for f in (v.get("findings") or [])[:12]:
                    print(f"   ⚑ {str(f)[:160]}")

        # ---- trạng thái + lý do cuối ----
        last_state = [e for e in events if e["type"] == "state_changed"][-1]
        print(f"\n===== KẾT LUẬN HỆ THỐNG =====")
        print(f"  Trạng thái: {last_state['payload'].get('state')}")
        if last_state["payload"].get("reason"):
            print(f"  Lý do: {last_state['payload']['reason'][:300]}")
        print(f"  Tổng events ghi nhận: {len(events)}")


if __name__ == "__main__":
    asyncio.run(main())
