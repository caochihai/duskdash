"""Validation & Recommendation Agent — chốt chất lượng trước khi trình người duyệt.

Bước 1: xác thực facts/evidence/nhất quán giữa các verdict.
Bước 2: nếu mâu thuẫn -> CHALLENGE trực tiếp agent liên quan qua A2A (tối đa
        MAX_CHALLENGE_ROUNDS vòng, máy tự giải trước khi phiền con người).
Bước 3: tổng hợp khuyến nghị có cấu trúc cho Approval Package.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base import a2a_send, build_agent_app  # noqa: E402
from common import config  # noqa: E402
from common.schemas import (  # noqa: E402
    AgentCard, AgentSkill, Envelope, Evidence, MessageType, Verdict, VerdictDecision,
)

CARD = AgentCard(
    agent_id="validation",
    name="Validation & Recommendation Agent",
    description="Kiểm chứng chéo kết luận của các chuyên gia: facts, evidence, "
                "citations, nhất quán; điều phối challenge giữa các agent; "
                "tổng hợp khuyến nghị trình phê duyệt.",
    url=config.agent_url("validation"),
    skills=[
        AgentSkill(id="fact_check", name="Xác thực kết luận",
                   description="Kiểm tra evidence, tính nhất quán giữa các verdict"),
        AgentSkill(id="recommend", name="Tổng hợp khuyến nghị",
                   description="Tạo khuyến nghị có cấu trúc kèm điều kiện"),
    ],
)


def _find_conflict(verdicts: dict[str, Verdict]) -> dict | None:
    """Phát hiện mâu thuẫn giữa các verdict — trả về challenge cần gửi (nếu có)."""
    credit = verdicts.get("credit")
    compliance = verdicts.get("compliance")
    if (
        credit and compliance
        and credit.proposed_limit and compliance.max_secured_limit
        and credit.proposed_limit > compliance.max_secured_limit + 1  # sai số float
    ):
        return {
            "target": "credit",
            "reason": (
                f"Hạn mức đề xuất {credit.proposed_limit:,.0f} VND vượt giới hạn "
                f"cho vay có bảo đảm {compliance.max_secured_limit:,.0f} VND "
                f"(LTV {config.LTV_MAX:.0%} theo chính sách)"
            ),
            "max_secured_limit": compliance.max_secured_limit,
        }
    return None


async def handle_task(env: Envelope) -> Verdict:
    raw = env.payload.get("params", {}).get("verdicts", {})
    verdicts: dict[str, Verdict] = {k: Verdict(**v) for k, v in raw.items()}

    trace: list[str] = []
    challenge_rounds = 0

    # ---- Bước 1: xác thực cơ bản ----
    issues: list[str] = []
    for name, v in verdicts.items():
        if name in ("credit", "compliance") and not v.evidence:
            issues.append(f"Verdict của {name} thiếu evidence/citation")
    trace.append(f"Xác thực {len(verdicts)} verdict: {len(issues)} vấn đề evidence")

    # ---- Bước 2: vòng challenge máy-tự-giải ----
    while challenge_rounds < config.MAX_CHALLENGE_ROUNDS:
        conflict = _find_conflict(verdicts)
        if conflict is None:
            break
        challenge_rounds += 1
        trace.append(
            f"Vòng {challenge_rounds}: CHALLENGE {conflict['target']} — {conflict['reason']}"
        )
        resp = await a2a_send(CARD.agent_id, conflict["target"], Envelope(
            case_id=env.case_id, task_id=env.task_id,
            from_agent=CARD.agent_id, to_agent=conflict["target"],
            type=MessageType.CHALLENGE,
            payload={"reason": conflict["reason"],
                     "max_secured_limit": conflict["max_secured_limit"]},
        ))
        if resp.type == MessageType.CHALLENGE_RESPONSE and "verdict" in resp.payload:
            verdicts[conflict["target"]] = Verdict(**resp.payload["verdict"])
            trace.append(
                f"{conflict['target']} đã điều chỉnh: "
                f"{verdicts[conflict['target']].summary}"
            )
        else:
            trace.append(f"{conflict['target']} không phản hồi hợp lệ — dừng vòng challenge")
            break

    unresolved = _find_conflict(verdicts)

    # ---- Bước 3: tổng hợp khuyến nghị ----
    decisions = {name: v.decision for name, v in verdicts.items()}
    all_conditions = [c for v in verdicts.values() for c in v.conditions]
    all_findings = [f for v in verdicts.values() for f in v.findings]
    credit = verdicts.get("credit")

    if VerdictDecision.REJECT in decisions.values():
        rec_decision, rec = VerdictDecision.REJECT, "TỪ CHỐI: có chuyên gia kết luận không đạt điều kiện"
    elif unresolved is not None or issues:
        rec_decision = VerdictDecision.NEED_MORE_INFO
        rec = "ESCALATE: mâu thuẫn không tự giải được sau vòng challenge hoặc thiếu evidence"
    elif VerdictDecision.NEED_MORE_INFO in decisions.values():
        rec_decision, rec = VerdictDecision.NEED_MORE_INFO, "CẦN BỔ SUNG: hồ sơ chưa đủ để trình phê duyệt"
    else:
        rec_decision = VerdictDecision.APPROVE
        limit_txt = f" hạn mức {credit.proposed_limit:,.0f} VND" if credit and credit.proposed_limit else ""
        flag_txt = " (có yếu tố cần cấp thẩm quyền lưu ý)" if VerdictDecision.FLAG in decisions.values() else ""
        rec = f"ĐỀ XUẤT PHÊ DUYỆT{limit_txt}{flag_txt}"

    # LLM narrative (hybrid/llm): diễn giải facts đã chốt thành khuyến nghị điều hành
    # — KHÔNG thay đổi quyết định/con số, chỉ viết lời văn cho người duyệt.
    narrative = await _synthesize_narrative(rec_decision, rec, verdicts, trace)

    return Verdict(
        agent=CARD.agent_id, task_id=env.task_id or "",
        decision=rec_decision,
        summary=rec,
        findings=all_findings,
        conditions=list(dict.fromkeys(all_conditions)),  # khử trùng lặp, giữ thứ tự
        proposed_limit=credit.proposed_limit if credit else None,
        evidence=[Evidence(source="validation", quote=t) for t in trace],
        data={
            "final_verdicts": {k: v.model_dump(mode="json") for k, v in verdicts.items()},
            "challenge_rounds": challenge_rounds,
            "issues": issues,
            "narrative": narrative,
        },
    )


async def _synthesize_narrative(rec_decision, rec: str,
                                verdicts: dict, trace: list[str]) -> str:
    """Dùng LLM (gpt-oss-120b) viết khuyến nghị điều hành từ facts đã chốt.
    An toàn: chỉ diễn giải, quyết định & con số do rules quyết. Fail -> trả rec gốc."""
    if config.LLM_MODE not in ("llm", "hybrid"):
        return rec
    from common import llm

    facts = {
        name: {"decision": v.decision.value, "summary": v.summary,
               "proposed_limit": v.proposed_limit,
               "max_secured_limit": v.max_secured_limit,
               "findings": v.findings, "conditions": v.conditions}
        for name, v in verdicts.items()
    }
    try:
        data = await llm.chat_json(
            system="Bạn là thư ký hội đồng tín dụng SHB. Dựa TRÊN CÁC FACTS đã được "
                   "các chuyên gia chốt (không được thay đổi quyết định hay con số), "
                   "viết một khuyến nghị điều hành ngắn gọn, mạch lạc bằng tiếng Việt "
                   "cho cấp phê duyệt. Nêu rõ: kết luận, hạn mức (nếu có), lý do chính, "
                   "và điểm cần lưu ý. Trả JSON {\"narrative\": string}.",
            user=f"Quyết định tổng hợp: {rec_decision.value} ({rec})\n"
                 f"Facts theo chuyên gia: {facts}\n"
                 f"Nhật ký kiểm chứng & challenge: {trace}",
            schema_hint='{"narrative": string}',
        )
        return data.get("narrative", rec) or rec
    except Exception:  # noqa: BLE001
        return rec


app = build_agent_app(CARD, handle_task)
