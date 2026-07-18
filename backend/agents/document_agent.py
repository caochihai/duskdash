"""Document Intelligence Agent — trích xuất tài liệu bằng vision-LLM + cross-check.

Rules mode: dùng dữ liệu đã trích xuất sẵn trong payload (fixtures).
LLM mode:   gửi ảnh vào vision model, nhận JSON có cấu trúc theo schema từng loại.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base import build_agent_app  # noqa: E402
from common import config, llm, mcp_client  # noqa: E402
from common.schemas import (  # noqa: E402
    AgentCard, AgentSkill, Envelope, Evidence, Verdict, VerdictDecision,
)

CARD = AgentCard(
    agent_id="document",
    name="Document Intelligence Agent",
    description="Chuyên gia số về hồ sơ tài liệu: trích xuất ĐKKD, BCTC, sao kê, "
                "CCCD, sổ đỏ bằng vision-LLM và đối chiếu chéo giữa các tài liệu.",
    url=config.agent_url("document"),
    skills=[
        AgentSkill(id="extract_documents", name="Trích xuất tài liệu",
                   description="Đọc ảnh/scan tài liệu, trả về dữ liệu có cấu trúc"),
        AgentSkill(id="cross_check", name="Đối chiếu chéo",
                   description="So khớp thông tin giữa các tài liệu và dữ liệu core banking"),
    ],
)

# Schema trích xuất theo loại tài liệu (dùng cho vision-LLM)
DOC_SCHEMAS = {
    "dkkd": '{"company_name": str, "tax_code": str, "legal_rep_name": str, '
            '"business_lines": [str], "registered_capital": number}',
    "bctc": '{"year": int, "revenue": number, "ebitda": number, "total_debt": number, '
            '"equity": number}',
    # Sao kê: chỉ yêu cầu model đọc TỪNG DÒNG giao dịch — tổng/bình quân do CODE tính
    # (benchmark: VLM đọc số từng dòng 6/6 đúng nhưng 2/3 model tự cộng tổng SAI)
    "sao_ke": '{"account_number": str, "period_months": int, '
              '"transactions": [{"date": str, "amount": number}]}',
    # Phiếu thông tin khách hàng (bộ 6 hồ sơ demo chụp thật).
    # Benchmark gemma-4-31B: 97% — ràng buộc định dạng mã hồ sơ chống nhầm I/1.
    "phieu_tttd": '{"ma_ho_so": str (định dạng "CR-" + 1 CHỮ CÁI IN HOA + 2 chữ số, '
                  'vd CR-A01/CR-I03; ký tự sau "CR-" luôn là CHỮ CÁI, không phải số 1), '
                  '"loai": "doanh_nghiep"|"ca_nhan", "ten_khach_hang": str, '
                  '"nguoi_dai_dien": str|null, "san_pham": str, '
                  '"so_tien_de_nghi_ty": number, "de_xuat_so_bo": str, '
                  '"cic_nhom": int|null, '
                  '"doanh_thu_theo_nam_ty": [number]|null (DN: 2023,2024,2025), '
                  '"ebitda_theo_nam_ty": [number]|null, '
                  '"tong_thu_nhap_thang_trieu": number|null (cá nhân), '
                  '"dti_phan_tram": number|null (cá nhân), '
                  '"tong_gia_tri_tsdb_xu_ly_ty": number|null, '
                  '"nhan_xet_so_bo": [str]}',
    "cccd": '{"full_name": str, "id_number": str, "date_of_birth": str}',
    "so_do": '{"owner_name": str, "address": str, "area_m2": number, "certificate_no": str}',
}

# Lưu kết quả trích xuất theo case để phục vụ info_request từ agent khác
_extractions: dict[str, dict] = {}


def _normalize_ma_ho_so(data: dict) -> dict:
    """Chuẩn hóa mã hồ sơ bằng code theo định dạng CR-<chữ cái><2 số>:
    sửa các nhầm lẫn OCR phổ biến (1<->I, 0<->O, SR-<->CR-)."""
    import re

    raw = str(data.get("ma_ho_so") or "").upper().strip().replace(" ", "")
    if not raw:
        return data
    raw = re.sub(r"^[A-Z]R-?", "CR-", raw)  # SR-/GR-... đọc nhầm tiền tố
    m = re.match(r"^CR-(.)(\d{2})$", raw)
    if m:
        ch = {"1": "I", "0": "O"}.get(m.group(1), m.group(1))
        data["ma_ho_so"] = f"CR-{ch}{m.group(2)}"
    return data


def _derive_saoke_numbers(data: dict) -> dict:
    """Tổng/bình quân dòng tiền TÍNH BẰNG CODE từ line items — không tin LLM cộng số."""
    txns = data.get("transactions") or []
    amounts = []
    for t in txns:
        try:
            amounts.append(float(t.get("amount", 0) or 0))
        except (TypeError, ValueError):
            continue
    if amounts:
        total = sum(amounts)
        months = data.get("period_months") or 12
        data["total_inflow"] = total
        data["avg_monthly_inflow"] = total / months
        data["derived_by"] = "code"  # minh bạch trên dashboard/audit
    return data


async def _extract_one(doc: dict) -> tuple[str, dict]:
    dtype = doc.get("doc_type", "unknown")
    if "extracted" in doc:  # đã có dữ liệu cấu trúc (fixtures / đã trích xuất)
        data = doc["extracted"]
        if dtype == "sao_ke":
            data = _derive_saoke_numbers(data)
        return dtype, data
    if config.LLM_MODE in ("llm", "hybrid") and doc.get("image_path"):
        data = await llm.vision_extract(
            system=f"Bạn là chuyên viên nhập liệu ngân hàng. Trích xuất chính xác "
                   f"thông tin từ tài liệu loại '{dtype}'. Giữ nguyên dấu tiếng Việt. "
                   f"Chỉ trả về JSON đúng schema, không giải thích. "
                   f"Trường không đọc được để null.",
            image_path=doc["image_path"],
            schema_hint=DOC_SCHEMAS.get(dtype, "{}"),
        )
        if dtype == "sao_ke":
            data = _derive_saoke_numbers(data)
        if dtype == "phieu_tttd":
            data = _normalize_ma_ho_so(data)
        return dtype, data
    return dtype, {"error": "không có dữ liệu trích xuất (thiếu ảnh hoặc đang ở rules mode)"}


async def handle_task(env: Envelope) -> Verdict:
    documents = env.payload.get("params", {}).get("documents", [])
    request = env.payload.get("params", {}).get("request", {})
    business_id = request.get("business_id", "")

    extracted: dict[str, dict] = {}
    for doc in documents:
        dtype, data = await _extract_one(doc)
        extracted[dtype] = data
    _extractions[env.case_id] = extracted

    findings: list[str] = []
    evidence: list[Evidence] = []
    decision = VerdictDecision.PASS_

    # Cross-check 1: doanh thu BCTC vs dòng tiền về tài khoản trên sao kê
    bctc, sao_ke = extracted.get("bctc"), extracted.get("sao_ke")
    if bctc and sao_ke and bctc.get("revenue") and sao_ke.get("avg_monthly_inflow"):
        annual_inflow = sao_ke["avg_monthly_inflow"] * 12
        ratio = annual_inflow / bctc["revenue"]
        evidence.append(Evidence(
            source="BCTC + sao kê",
            quote=f"Doanh thu BCTC {bctc['revenue']:,.0f} vs dòng tiền về TK "
                  f"{annual_inflow:,.0f}/năm (tỷ lệ {ratio:.0%})",
        ))
        if ratio < 0.7:
            decision = VerdictDecision.FLAG
            findings.append(
                f"BẤT THƯỜNG: dòng tiền về tài khoản chỉ đạt {ratio:.0%} doanh thu "
                f"khai trên BCTC — cần giải trình trước khi dùng doanh thu làm cơ sở cấp hạn mức"
            )

    # Cross-check 2: người đại diện trên CCCD vs hồ sơ pháp nhân trong core banking
    cccd = extracted.get("cccd")
    if cccd and business_id:
        biz = await mcp_client.call_tool("get_business", {"business_id": business_id})
        if isinstance(biz, dict) and biz.get("legal_rep_name"):
            if cccd.get("full_name") and cccd["full_name"].strip() != biz["legal_rep_name"].strip():
                decision = VerdictDecision.FLAG
                findings.append(
                    f"LỆCH KYC: tên trên CCCD '{cccd['full_name']}' khác người đại diện "
                    f"pháp luật '{biz['legal_rep_name']}' trong hồ sơ pháp nhân"
                )
            else:
                evidence.append(Evidence(
                    source="CCCD + core banking",
                    quote=f"Tên người đại diện khớp: {biz['legal_rep_name']}",
                ))

    summary = (
        f"Đã trích xuất {len(extracted)} tài liệu"
        + (f"; {len(findings)} cảnh báo cần lưu ý" if findings else "; không phát hiện bất thường")
    )
    return Verdict(
        agent=CARD.agent_id, task_id=env.task_id or "", decision=decision,
        summary=summary, findings=findings, evidence=evidence,
        data={"extractions": extracted},
    )


async def handle_info(env: Envelope) -> dict:
    """Agent khác hỏi dữ liệu đã trích xuất (vd: Credit hỏi dòng tiền thực tế)."""
    extracted = _extractions.get(env.case_id, {})
    field = env.payload.get("field", "")
    if field == "verified_annual_inflow":
        sao_ke = extracted.get("sao_ke") or {}
        if sao_ke.get("avg_monthly_inflow"):
            return {"verified_annual_inflow": sao_ke["avg_monthly_inflow"] * 12}
        return {"verified_annual_inflow": None}
    return {"extractions": extracted}


app = build_agent_app(CARD, handle_task, handle_info=handle_info)
