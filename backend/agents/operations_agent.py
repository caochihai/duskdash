"""Operations Agent — hai pha tách biệt:

DRY-RUN (trước phê duyệt): kiểm tra điều kiện vận hành + tạo bản nháp, KHÔNG ghi.
COMMIT  (sau phê duyệt):   xác minh approval token + RE-CHECK preconditions
                           + idempotency key + đối soát khi kết quả mơ hồ
                           + retry đúng 1 lần, thất bại rõ ràng thì escalate.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from agents.base import build_agent_app  # noqa: E402
from common import config, mcp_client  # noqa: E402
from common.schemas import (  # noqa: E402
    AgentCard, AgentSkill, Envelope, Evidence, Verdict, VerdictDecision,
)
from pydantic import BaseModel  # noqa: E402
from tools.registry import SideEffect, ToolRegistry, ToolSpec  # noqa: E402
from tools.runner import ToolRunner  # noqa: E402


class CommitLoanArgs(BaseModel):
    idempotency_key: str
    case_id: str
    business_id: str
    amount: float
    term_months: int


class CommitLoanResult(BaseModel):
    loan_id: str
    already_recorded: bool = False


async def _commit_loan_tool(args: CommitLoanArgs) -> CommitLoanResult:
    result = await mcp_client.call_tool("commit_loan", args.model_dump())
    return CommitLoanResult.model_validate(result)


TOOL_REGISTRY = ToolRegistry()
TOOL_REGISTRY.register(ToolSpec(
    name="operations.commit_loan", args_model=CommitLoanArgs, result_model=CommitLoanResult,
    allowed_agents=frozenset({"operations"}), side_effect=SideEffect.WRITE,
    handler=_commit_loan_tool,
))
TOOL_RUNNER = ToolRunner(TOOL_REGISTRY)

CARD = AgentCard(
    agent_id="operations",
    name="Operations Agent",
    description="Chuyên gia số vận hành: kiểm tra điều kiện tác nghiệp, tạo draft "
                "hồ sơ vay (dry-run) và thực thi tạo khoản vay + lịch giải ngân (commit).",
    url=config.agent_url("operations"),
    skills=[
        AgentSkill(id="ops_dryrun", name="Kiểm tra vận hành + draft",
                   description="Xác minh tài khoản, điều kiện tác nghiệp, tạo bản nháp"),
        AgentSkill(id="ops_commit", name="Thực thi sau phê duyệt",
                   description="Xác minh token, re-check preconditions, tạo khoản vay idempotent"),
    ],
)


async def _dry_run(env: Envelope) -> Verdict:
    request = env.payload.get("params", {}).get("request", {})
    business_id = request["business_id"]
    biz = await mcp_client.call_tool("get_business", {"business_id": business_id})
    if not biz.get("account_number"):
        return Verdict(agent=CARD.agent_id, task_id=env.task_id or "",
                       decision=VerdictDecision.NEED_MORE_INFO,
                       summary="Doanh nghiệp chưa có tài khoản thanh toán tại ngân hàng — "
                               "cần mở tài khoản trước khi giải ngân")
    draft = await mcp_client.call_tool("create_loan_draft", {
        "case_id": env.case_id, "business_id": business_id,
        "amount": float(request["amount"]), "term_months": int(request["term_months"])})
    return Verdict(
        agent=CARD.agent_id, task_id=env.task_id or "",
        decision=VerdictDecision.PASS_,
        summary=f"Điều kiện vận hành đạt. Đã tạo bản nháp {draft['draft_id']} (chưa hiệu lực)",
        evidence=[Evidence(source="core-banking:create_loan_draft",
                           quote=f"draft_id={draft['draft_id']}, TK nhận vốn "
                                 f"{biz['account_number']}")],
        data={"draft_id": draft["draft_id"]},
    )


async def _verify_token(case_id: str, token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{config.GATEWAY_URL}/internal/tokens/verify",
                                 json={"case_id": case_id, "token": token})
        return resp.json()


async def _commit(env: Envelope) -> Verdict:
    p = env.payload.get("params", {})
    case_id = env.case_id
    token = p.get("approval_token", "")
    amount = float(p["approved_limit"])
    plan_version = int(p.get("plan_version", 1))
    request = p.get("request", {})
    business_id = request["business_id"]

    # 1. Xác minh approval token (gateway đối chiếu hash package + policy version + expiry)
    tv = await _verify_token(case_id, token)
    if not tv.get("valid"):
        return Verdict(agent=CARD.agent_id, task_id=env.task_id or "",
                       decision=VerdictDecision.FLAG,
                       summary=f"TOKEN VÔ HIỆU: {tv.get('reason')} — dừng thực thi, "
                               f"case quay lại luồng phê duyệt",
                       data={"stage": "token_verify", "reason": tv.get("reason")})

    # 2. RE-CHECK preconditions tại thời điểm thực thi (chống TOCTOU)
    cic = await mcp_client.call_tool("get_cic_status", {"business_id": business_id})
    if cic.get("overdue_amount", 0) > 0:
        return Verdict(
            agent=CARD.agent_id, task_id=env.task_id or "",
            decision=VerdictDecision.FLAG,
            summary=f"PRECONDITION FAIL: phát sinh nợ quá hạn "
                    f"{cic['overdue_amount']:,.0f} VND sau thời điểm phê duyệt "
                    f"({cic.get('note', '')}) — chặn thực thi, yêu cầu tái thẩm định",
            evidence=[Evidence(source="core-banking:get_cic_status",
                               quote=f"CIC nhóm {cic.get('cic_group')}, quá hạn "
                                     f"{cic.get('overdue_amount', 0):,.0f}")],
            data={"stage": "precondition", "cic": cic},
        )

    # 3. Commit idempotent + đối soát khi mơ hồ + retry đúng 1 lần
    idem_key = f"{case_id}:v{plan_version}"
    commit_args = {"idempotency_key": idem_key, "case_id": case_id,
                   "business_id": business_id, "amount": amount,
                   "term_months": int(request["term_months"])}
    loan = None
    for attempt in (1, 2):  # tối đa: 1 lần chính + 1 retry sau đối soát
        try:
            loan = (await TOOL_RUNNER.execute(
                agent_id="operations", phase="commit", tool_name="operations.commit_loan",
                raw_args=commit_args, case_state="Executing", approval_valid=True,
            )).model_dump()
            break
        except Exception as e:  # noqa: BLE001 - kết quả mơ hồ (timeout/mất kết nối)
            recon = await mcp_client.call_tool(
                "get_loan_by_idempotency", {"idempotency_key": idem_key})
            if recon.get("found"):
                loan = recon["loan"]  # đã ghi nhận -> coi như thành công
                break
            if attempt == 2:
                return Verdict(
                    agent=CARD.agent_id, task_id=env.task_id or "",
                    decision=VerdictDecision.FLAG,
                    summary=f"Thực thi thất bại sau đối soát + 1 retry ({e}) — "
                            f"KHÔNG retry thêm, chuyển Escalated",
                    data={"stage": "commit_failed", "error": str(e)},
                )

    schedule = await mcp_client.call_tool(
        "create_disbursement_schedule", {"loan_id": loan["loan_id"], "num_tranches": 2})

    return Verdict(
        agent=CARD.agent_id, task_id=env.task_id or "",
        decision=VerdictDecision.PASS_,
        summary=f"Đã tạo khoản vay {loan['loan_id']} số tiền {amount:,.0f} VND "
                f"và lịch giải ngân {schedule['tranches']} đợt"
                + (" (idempotent: bản ghi đã tồn tại, không tạo trùng)"
                   if loan.get("already_recorded") else ""),
        evidence=[Evidence(source="core-banking:commit_loan",
                           quote=f"loan_id={loan['loan_id']}, idempotency_key={idem_key}")],
        data={"loan_id": loan["loan_id"], "schedule": schedule},
    )


async def handle_task(env: Envelope) -> Verdict:
    phase = env.payload.get("params", {}).get("phase", "dry_run")
    if phase == "commit":
        return await _commit(env)
    return await _dry_run(env)


app = build_agent_app(CARD, handle_task)
