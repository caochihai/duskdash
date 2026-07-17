"""Credit Agent — chuyên gia thẩm định tín dụng SME.

Phân tích BCTC (DSCR, đòn bẩy), đề xuất hạn mức; hỏi Document Agent về dòng tiền
thực tế (A2A info_request); tự điều chỉnh verdict khi bị challenge (A2A).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base import a2a_send, build_agent_app  # noqa: E402
from common import config, llm, mcp_client, rag  # noqa: E402
from common.schemas import (  # noqa: E402
    AgentCard, AgentSkill, Envelope, Evidence, MessageType, Verdict, VerdictDecision,
)

CARD = AgentCard(
    agent_id="credit",
    name="Credit Agent",
    description="Chuyên gia số thẩm định tín dụng: phân tích BCTC, DSCR, đòn bẩy, "
                "dư nợ hiện hữu; đề xuất hạn mức và điều kiện cấp tín dụng.",
    url=config.agent_url("credit"),
    skills=[
        AgentSkill(id="financial_analysis", name="Phân tích tài chính",
                   description="DSCR, đòn bẩy, vốn lưu động, dòng tiền"),
        AgentSkill(id="limit_proposal", name="Đề xuất hạn mức",
                   description="Đề xuất hạn mức + điều kiện theo chính sách tín dụng"),
    ],
)

_last_verdict: dict[str, Verdict] = {}


async def _rules_task(env: Envelope) -> Verdict:
    request = env.payload.get("params", {}).get("request", {})
    business_id = request["business_id"]
    amount = float(request["amount"])

    fins = await mcp_client.call_tool("get_financials", {"business_id": business_id})
    loans = await mcp_client.call_tool("get_existing_loans", {"business_id": business_id})
    if not fins:
        return Verdict(agent=CARD.agent_id, task_id=env.task_id or "",
                       decision=VerdictDecision.NEED_MORE_INFO,
                       summary="Không có số liệu tài chính — yêu cầu bổ sung BCTC")
    latest = max(fins, key=lambda f: f["year"])
    dscr = latest["ebitda"] / latest["debt_service"] if latest["debt_service"] else 99
    leverage = latest["total_debt"] / latest["equity"] if latest["equity"] else 99

    evidence = [
        Evidence(source="core-banking:get_financials",
                 quote=f"Năm {latest['year']}: doanh thu {latest['revenue']:,.0f}, "
                       f"EBITDA {latest['ebitda']:,.0f}, DSCR {dscr:.2f}, đòn bẩy {leverage:.2f}"),
    ]
    for p in rag.search("credit", "DSCR tối thiểu hạn mức vốn lưu động doanh thu"):
        evidence.append(Evidence(source=f"RAG:{p['title']} {p['version']} {p['section']}", quote=p["quote"]))

    findings: list[str] = []
    conditions: list[str] = []
    revenue_basis = latest["revenue"]

    # A2A: hỏi Document Agent dòng tiền thực tế về tài khoản để đối chiếu doanh thu
    try:
        resp = await a2a_send(CARD.agent_id, "document", Envelope(
            case_id=env.case_id, task_id=env.task_id,
            from_agent=CARD.agent_id, to_agent="document",
            type=MessageType.INFO_REQUEST,
            payload={"field": "verified_annual_inflow"},
        ))
        inflow = resp.payload.get("verified_annual_inflow")
        if inflow and inflow < revenue_basis * 0.7:
            revenue_basis = inflow
            findings.append(
                f"Dòng tiền thực tế về TK ({inflow:,.0f}/năm) thấp hơn nhiều doanh thu BCTC "
                f"— dùng dòng tiền thực tế làm cơ sở tính hạn mức (nguyên tắc thận trọng)"
            )
    except Exception:  # noqa: BLE001 - document agent chưa có dữ liệu thì bỏ qua
        pass

    proposed = min(amount, 0.25 * revenue_basis)

    if dscr < 1.0:
        decision = VerdictDecision.REJECT
        summary = f"DSCR {dscr:.2f} < 1.0: không đủ khả năng trả nợ — từ chối"
    elif dscr < config.DSCR_MIN:
        decision = VerdictDecision.NEED_MORE_INFO
        summary = (f"DSCR {dscr:.2f} dưới ngưỡng {config.DSCR_MIN} — cần phương án "
                   f"kinh doanh/nguồn trả nợ bổ sung trước khi trình")
    else:
        decision = VerdictDecision.APPROVE
        summary = (f"Đủ điều kiện tín dụng. Đề xuất hạn mức {proposed:,.0f} VND "
                   f"(DSCR {dscr:.2f}, đòn bẩy {leverage:.2f})")
        conditions.append("Bổ sung BCTC quý gần nhất trước giải ngân đợt 2")
    if leverage > 2.0:
        findings.append(f"Đòn bẩy {leverage:.2f} > 2.0 — theo dõi sát")
    if loans:
        findings.append(f"Đang có {len(loans)} khoản vay hiện hữu tại ngân hàng")

    verdict = Verdict(
        agent=CARD.agent_id, task_id=env.task_id or "", decision=decision,
        summary=summary, evidence=evidence, findings=findings, conditions=conditions,
        proposed_limit=proposed if decision == VerdictDecision.APPROVE else None,
        data={"dscr": round(dscr, 2), "leverage": round(leverage, 2),
              "revenue_basis": revenue_basis},
    )
    _last_verdict[env.case_id] = verdict
    return verdict


async def _llm_task(env: Envelope) -> Verdict:
    request = env.payload.get("params", {}).get("request", {})
    business_id = request["business_id"]

    async def t_financials() -> list:
        return await mcp_client.call_tool("get_financials", {"business_id": business_id})

    async def t_loans() -> list:
        return await mcp_client.call_tool("get_existing_loans", {"business_id": business_id})

    async def t_policy(query: str) -> list:
        return rag.search("credit", query)

    async def t_ask_document(field: str) -> dict:
        resp = await a2a_send(CARD.agent_id, "document", Envelope(
            case_id=env.case_id, task_id=env.task_id, from_agent=CARD.agent_id,
            to_agent="document", type=MessageType.INFO_REQUEST, payload={"field": field}))
        return resp.payload

    tools = [
        llm.ToolDef("get_financials", "Số liệu tài chính doanh nghiệp",
                    {"type": "object", "properties": {}}, t_financials),
        llm.ToolDef("get_existing_loans", "Khoản vay hiện hữu",
                    {"type": "object", "properties": {}}, t_loans),
        llm.ToolDef("search_credit_policy", "Tra cứu chính sách tín dụng nội bộ",
                    {"type": "object", "properties": {"query": {"type": "string"}},
                     "required": ["query"]}, t_policy),
        llm.ToolDef("ask_document_agent",
                    "Hỏi Document Agent (field: verified_annual_inflow)",
                    {"type": "object", "properties": {"field": {"type": "string"}},
                     "required": ["field"]}, t_ask_document),
        llm.ToolDef("submit_verdict", "Nộp kết luận thẩm định cuối cùng",
                    {"type": "object", "properties": {
                        "decision": {"type": "string",
                                     "enum": ["approve", "reject", "need_more_info"]},
                        "summary": {"type": "string"},
                        "proposed_limit": {"type": "number"},
                        "findings": {"type": "array", "items": {"type": "string"}},
                        "conditions": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "array", "items": {"type": "object", "properties": {
                            "source": {"type": "string"}, "quote": {"type": "string"}}}},
                    }, "required": ["decision", "summary"]}, None),  # type: ignore[arg-type]
    ]
    result = await llm.tool_loop(
        system=f"Bạn là chuyên gia thẩm định tín dụng SME của ngân hàng SHB. "
               f"Phân tích DSCR (tối thiểu {config.DSCR_MIN}), đòn bẩy, dòng tiền. "
               f"LUÔN đối chiếu dòng tiền thực tế qua ask_document_agent và trích dẫn "
               f"chính sách qua search_credit_policy. Kết thúc bằng submit_verdict.",
        user=f"Thẩm định đề nghị vay: {request}",
        tools=tools,
    )
    verdict = Verdict.from_llm(CARD.agent_id, env.task_id or "", result)
    _last_verdict[env.case_id] = verdict
    return verdict


async def handle_task(env: Envelope) -> Verdict:
    if config.LLM_MODE == "llm":
        return await _llm_task(env)
    return await _rules_task(env)


async def handle_challenge(env: Envelope) -> Verdict:
    """Nhận challenge từ Validation Agent -> tự điều chỉnh verdict + ghi lý do."""
    prev = _last_verdict.get(env.case_id)
    cap = env.payload.get("max_secured_limit")
    reason = env.payload.get("reason", "")
    if prev is None or cap is None:
        return Verdict(agent=CARD.agent_id, task_id=env.task_id or "",
                       decision=VerdictDecision.NEED_MORE_INFO,
                       summary=f"Không thể xử lý challenge: {reason}")
    new_limit = min(prev.proposed_limit or cap, float(cap))
    revised = prev.model_copy(update={
        "proposed_limit": new_limit,
        "summary": f"[ĐÃ ĐIỀU CHỈNH] Hạn mức đề xuất {new_limit:,.0f} VND "
                   f"(giảm từ {prev.proposed_limit:,.0f}) theo giới hạn bảo đảm",
        "revision_of": prev.task_id,
        "revision_reason": f"Chấp nhận challenge: {reason}",
    })
    _last_verdict[env.case_id] = revised
    return revised


app = build_agent_app(CARD, handle_task, handle_challenge=handle_challenge)
