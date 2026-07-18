"""Demo E2E: hồ sơ B001 (An Bình) — luồng sạch có twist challenge hạn mức.

Chạy: python -m scripts.demo_run          (sau khi run_all.py đang chạy)
      python -m scripts.demo_run --b002   (hồ sơ gài: DSCR thấp + lệch dòng tiền)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from common import config  # noqa: E402

G = config.GATEWAY_URL

B001_CASE = {
    "request": {"business_id": "B001", "amount": 5_000_000_000, "term_months": 12,
                "purpose": "Bổ sung vốn lưu động sản xuất bao bì",
                "has_collateral": True, "collateral_id": "C001"},
    "submitted_by": "chuyen_vien_A",
    "documents": [
        {"doc_type": "bctc", "extracted": {"year": 2025, "revenue": 22e9,
                                           "ebitda": 2.9e9, "total_debt": 3.2e9, "equity": 8.8e9}},
        {"doc_type": "sao_ke", "extracted": {"account_number": "010203040506",
                                             "period_months": 12, "total_inflow": 21.0e9,
                                             "avg_monthly_inflow": 1.75e9}},
        {"doc_type": "cccd", "extracted": {"full_name": "Nguyễn Văn An",
                                           "id_number": "079088001234",
                                           "date_of_birth": "1988-03-12"}},
    ],
}

B002_CASE = {
    "request": {"business_id": "B002", "amount": 3_000_000_000, "term_months": 9,
                "purpose": "Vốn lưu động thi công công trình", "has_collateral": False},
    "submitted_by": "chuyen_vien_B",
    "documents": [
        {"doc_type": "bctc", "extracted": {"year": 2025, "revenue": 18e9,
                                           "ebitda": 1.5e9, "total_debt": 6.5e9, "equity": 3.0e9}},
        {"doc_type": "sao_ke", "extracted": {"account_number": "060504030201",
                                             "period_months": 12, "total_inflow": 7.5e9,
                                             "avg_monthly_inflow": 0.625e9}},
    ],
}


async def wait_state(client: httpx.AsyncClient, case_id: str, targets: set[str],
                     timeout: float = 300) -> str:
    for _ in range(int(timeout)):
        case = (await client.get(f"{G}/cases/{case_id}")).json()
        if case.get("state") in targets:
            return case["state"]
        await asyncio.sleep(1)
    raise TimeoutError(f"case không đạt {targets} sau {timeout}s")


async def print_events(client: httpx.AsyncClient, case_id: str) -> None:
    events = (await client.get(f"{G}/cases/{case_id}/events")).json()
    print(f"\n===== TRACE ({len(events)} events) =====")
    for e in events:
        p = e["payload"]
        detail = p.get("state") or p.get("rationale") or p.get("summary") \
            or p.get("reason") or (p.get("verdict") or {}).get("summary") or ""
        print(f"  [{e['agent']:>12}] {e['type']:<28} {str(detail)[:100]}")


async def main() -> None:
    case_body = B002_CASE if "--b002" in sys.argv else B001_CASE
    async with httpx.AsyncClient(timeout=30) as client:
        r = (await client.post(f"{G}/cases", json=case_body)).json()
        case_id = r["case_id"]
        print(f"Case: {case_id} — {case_body['request']['business_id']}, "
              f"đề nghị {case_body['request']['amount']:,.0f} VND")

        await client.post(f"{G}/cases/{case_id}/run")
        state = await wait_state(client, case_id,
                                 {"Pending Approval", "Needs Info", "Rejected", "Escalated"})
        print(f"\n>> Trạng thái sau phân tích: {state}")

        case = (await client.get(f"{G}/cases/{case_id}")).json()
        pkg = case.get("package")
        if pkg:
            print(f">> Khuyến nghị: {pkg['recommendation']}")
            print(f">> Điều kiện: {pkg['conditions']}")
            print(f">> Cấp phê duyệt: {pkg['required_approver_level']}")

        if state == "Pending Approval":
            print("\n>> HITL: Giám đốc chi nhánh phê duyệt...")
            await client.post(f"{G}/cases/{case_id}/approve",
                              json={"approver": "giam_doc_chi_nhanh_Le_Thi_Mai",
                                    "approver_level": pkg["required_approver_level"]})
            state = await wait_state(client, case_id,
                                     {"Completed", "Escalated", "Pending Approval"})
            print(f">> Trạng thái cuối: {state}")

        await print_events(client, case_id)

        audit = (await client.get(f"{G}/audit/mcp?limit=10")).json()
        print(f"\n===== MCP AUDIT (10 tool call gần nhất) =====")
        for a in audit:
            print(f"  {a['tool']:<30} {a['args_json'][:70]}")


if __name__ == "__main__":
    asyncio.run(main())
