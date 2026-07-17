"""Compliance Agent — chuyên gia pháp chế & tuân thủ.

KYB, blacklist/AML, CIC, thẩm định pháp lý TSĐB; tính giới hạn cho vay có bảo đảm
(max_secured_limit = LTV_MAX x định giá) — đầu vào cho vòng challenge của Validation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base import build_agent_app  # noqa: E402
from common import config, llm, mcp_client, rag  # noqa: E402
from common.schemas import (  # noqa: E402
    AgentCard, AgentSkill, Envelope, Evidence, Verdict, VerdictDecision,
)

CARD = AgentCard(
    agent_id="compliance",
    name="Legal & Compliance Agent",
    description="Chuyên gia số pháp chế & tuân thủ: KYB, AML/blacklist, CIC, "
                "thẩm định pháp lý tài sản bảo đảm, giới hạn LTV.",
    url=config.agent_url("compliance"),
    skills=[
        AgentSkill(id="kyb_aml", name="KYB & AML",
                   description="Xác minh pháp nhân, người đại diện, danh sách đen, CIC"),
        AgentSkill(id="collateral_legal", name="Pháp lý TSĐB",
                   description="Kiểm tra trạng thái pháp lý tài sản và giới hạn LTV"),
    ],
)


async def _rules_task(env: Envelope) -> Verdict:
    params = env.payload.get("params", {})
    request = params.get("request", {})
    business_id = request["business_id"]
    check_collateral = params.get("check_collateral", request.get("has_collateral", False))

    biz = await mcp_client.call_tool("get_business", {"business_id": business_id})
    bl = await mcp_client.call_tool("check_blacklist", {
        "name": biz.get("legal_rep_name", ""), "cccd": biz.get("legal_rep_cccd", "")})
    cic = await mcp_client.call_tool("get_cic_status", {"business_id": business_id})

    evidence = [
        Evidence(source="core-banking:get_business",
                 quote=f"{biz.get('name')} — MST {biz.get('tax_code')}, "
                       f"đại diện: {biz.get('legal_rep_name')}"),
        Evidence(source="core-banking:get_cic_status",
                 quote=f"CIC nhóm {cic.get('cic_group')}, quá hạn {cic.get('overdue_amount', 0):,.0f}"),
    ]
    for p in rag.search("compliance", "KYB danh sách đen AML nhóm nợ LTV tài sản bảo đảm"):
        evidence.append(Evidence(source=f"RAG:{p['source']}", quote=p["text"][:300]))

    findings: list[str] = []
    conditions: list[str] = []

    if bl.get("hit"):
        return Verdict(
            agent=CARD.agent_id, task_id=env.task_id or "",
            decision=VerdictDecision.REJECT,
            summary=f"HARD STOP: người đại diện có tên trong danh sách đen AML "
                    f"({bl['detail'].get('reason', '')}) — từ chối, không cần thẩm định tiếp",
            evidence=evidence, confidence=1.0,
        )

    decision = VerdictDecision.APPROVE
    if cic.get("cic_group", 1) >= 3:
        decision = VerdictDecision.REJECT
        findings.append(f"CIC nhóm {cic['cic_group']}: không đủ điều kiện cấp tín dụng")
    elif cic.get("cic_group", 1) == 2:
        decision = VerdictDecision.FLAG
        findings.append("CIC nhóm 2: cần phê duyệt cấp cao hơn và điều kiện tăng cường")
        conditions.append("Bổ sung giải trình lịch sử nợ nhóm 2 và nguồn trả nợ")

    if biz.get("industry_risk") == "high":
        findings.append(f"Ngành '{biz.get('industry')}' thuộc nhóm rủi ro cao theo khẩu vị rủi ro")
        conditions.append("Áp dụng tỷ lệ tài trợ thận trọng cho ngành rủi ro cao")

    max_secured = None
    if check_collateral:
        cols = await mcp_client.call_tool("get_collateral", {"business_id": business_id})
        if not cols:
            decision = VerdictDecision.NEED_MORE_INFO
            findings.append("Khai có TSĐB nhưng không tìm thấy hồ sơ tài sản")
        else:
            col = cols[0]
            if col["legal_status"] != "clear":
                decision = VerdictDecision.NEED_MORE_INFO
                findings.append(f"TSĐB {col['collateral_id']} chưa hoàn thiện pháp lý: "
                                f"{col['legal_status']}")
            else:
                max_secured = config.LTV_MAX * col["valuation"]
                evidence.append(Evidence(
                    source="core-banking:get_collateral",
                    quote=f"{col['description']} — định giá {col['valuation']:,.0f}, "
                          f"pháp lý rõ ràng. Giới hạn bảo đảm (LTV {config.LTV_MAX:.0%}): "
                          f"{max_secured:,.0f} VND"))
                conditions.append("Hoàn thiện đăng ký giao dịch bảo đảm trước giải ngân")

    summary = {
        VerdictDecision.APPROVE: "Đạt các kiểm tra tuân thủ KYB/AML/CIC",
        VerdictDecision.FLAG: "Đạt có điều kiện — tồn tại yếu tố rủi ro cần cấp thẩm quyền lưu ý",
        VerdictDecision.REJECT: "Không đạt điều kiện tuân thủ",
        VerdictDecision.NEED_MORE_INFO: "Thiếu hồ sơ pháp lý — cần bổ sung",
    }[decision]
    if max_secured:
        summary += f". Giới hạn cho vay có bảo đảm: {max_secured:,.0f} VND"

    return Verdict(
        agent=CARD.agent_id, task_id=env.task_id or "", decision=decision,
        summary=summary, evidence=evidence, findings=findings, conditions=conditions,
        max_secured_limit=max_secured,
        data={"cic_group": cic.get("cic_group"), "blacklist_hit": False},
    )


async def _llm_task(env: Envelope) -> Verdict:
    params = env.payload.get("params", {})
    request = params.get("request", {})
    business_id = request["business_id"]

    async def t_biz() -> dict:
        return await mcp_client.call_tool("get_business", {"business_id": business_id})

    async def t_blacklist(name: str, cccd: str = "") -> dict:
        return await mcp_client.call_tool("check_blacklist", {"name": name, "cccd": cccd})

    async def t_cic() -> dict:
        return await mcp_client.call_tool("get_cic_status", {"business_id": business_id})

    async def t_collateral() -> list:
        return await mcp_client.call_tool("get_collateral", {"business_id": business_id})

    async def t_policy(query: str) -> list:
        return rag.search("compliance", query)

    tools = [
        llm.ToolDef("get_business", "Hồ sơ pháp nhân", {"type": "object", "properties": {}}, t_biz),
        llm.ToolDef("check_blacklist", "Tra danh sách đen AML",
                    {"type": "object", "properties": {"name": {"type": "string"},
                     "cccd": {"type": "string"}}, "required": ["name"]}, t_blacklist),
        llm.ToolDef("get_cic_status", "Tra CIC", {"type": "object", "properties": {}}, t_cic),
        llm.ToolDef("get_collateral", "Hồ sơ TSĐB", {"type": "object", "properties": {}}, t_collateral),
        llm.ToolDef("search_compliance_policy", "Tra cứu quy định tuân thủ nội bộ",
                    {"type": "object", "properties": {"query": {"type": "string"}},
                     "required": ["query"]}, t_policy),
        llm.ToolDef("submit_verdict", "Nộp kết luận tuân thủ",
                    {"type": "object", "properties": {
                        "decision": {"type": "string",
                                     "enum": ["approve", "reject", "need_more_info", "flag"]},
                        "summary": {"type": "string"},
                        "max_secured_limit": {"type": "number"},
                        "findings": {"type": "array", "items": {"type": "string"}},
                        "conditions": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "array", "items": {"type": "object", "properties": {
                            "source": {"type": "string"}, "quote": {"type": "string"}}}},
                    }, "required": ["decision", "summary"]}, None),  # type: ignore[arg-type]
    ]
    result = await llm.tool_loop(
        system=f"Bạn là chuyên gia pháp chế & tuân thủ ngân hàng SHB. Kiểm tra KYB, "
               f"blacklist (hit = từ chối ngay), CIC (nhóm >=3 từ chối, nhóm 2 flag), "
               f"pháp lý TSĐB (LTV tối đa {config.LTV_MAX:.0%} — tính max_secured_limit). "
               f"Trích dẫn quy định qua search_compliance_policy. Kết thúc bằng submit_verdict.",
        user=f"Kiểm tra tuân thủ đề nghị vay: {request}, "
             f"kiểm tra TSĐB: {params.get('check_collateral', False)}",
        tools=tools,
    )
    return Verdict.from_llm(CARD.agent_id, env.task_id or "", result)


async def handle_task(env: Envelope) -> Verdict:
    if config.LLM_MODE == "llm":
        return await _llm_task(env)
    return await _rules_task(env)


app = build_agent_app(CARD, handle_task)
