"""Orchestrator: Plan Executor (topo-sort DAG, chạy song song) + state machine case.

Luồng: In Analysis -> (DAG: doc -> credit ∥ compliance -> ops dry-run -> validation
với vòng challenge) -> Pending Approval -> [HITL] -> Executing (commit) -> Completed.
Re-plan có giới hạn; vượt giới hạn -> Escalated.
"""
from __future__ import annotations

import asyncio
import traceback

import httpx

from common import config
from common.schemas import (
    ApprovalPackage, CaseState, Envelope, MessageType, Plan, Verdict, VerdictDecision,
)
from . import approval, db, planner
from .replanning import invalidated_tasks


async def _emit(case_id: str, agent: str, etype: str, payload: dict | None = None):
    from .main import broadcast  # import trễ để tránh vòng

    await broadcast(db.add_event(case_id, agent, etype, payload or {}))


def _set_state(case_id: str, state: CaseState) -> None:
    db.update_case(case_id, state=state.value)


async def _dispatch(case_id: str, task_id: str, agent: str, payload: dict) -> Verdict:
    """Gửi task_request A2A tới agent, nhận task_result."""
    env = Envelope(case_id=case_id, task_id=task_id, from_agent="orchestrator",
                   to_agent=agent, type=MessageType.TASK_REQUEST, payload=payload)
    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(f"{config.agent_url(agent)}/a2a",
                                 json=env.model_dump(mode="json"))
        resp.raise_for_status()
    reply = Envelope(**resp.json())
    if reply.type == MessageType.ERROR:
        raise RuntimeError(f"{agent} lỗi: {reply.payload.get('error')}")
    return Verdict(**reply.payload["verdict"])


async def run_analysis(case_id: str) -> None:
    """Chạy một vòng phân tích đầy đủ (plan -> DAG -> validation -> package)."""
    case = db.get_case(case_id)
    if case is None:
        return
    payload = case["payload"]
    version = case["replan_count"] + 1

    try:
        _set_state(case_id, CaseState.IN_ANALYSIS)
        await _emit(case_id, "orchestrator", "state_changed",
                    {"state": CaseState.IN_ANALYSIS.value})

        plan, source = await planner.make_plan(case_id, payload, version)
        db.save_plan(case_id, version, plan.model_dump(mode="json"))
        await _emit(case_id, "planner", "plan_created",
                    {"version": version, "source": source,
                     "rationale": plan.rationale,
                     "tasks": [t.model_dump(mode="json") for t in plan.tasks]})

        verdicts, verdict_by_agent = await _execute_dag(case_id, plan)

        # Tìm theo AGENT, không theo task_id (Planner LLM có thể đặt task_id tuỳ ý)
        validation = verdict_by_agent.get("validation")
        if validation is None:
            raise RuntimeError("thiếu verdict validation")

        if validation.decision == VerdictDecision.APPROVE:
            await _build_package(case_id, plan, validation)
        elif validation.decision == VerdictDecision.REJECT:
            _set_state(case_id, CaseState.REJECTED)
            await _emit(case_id, "orchestrator", "state_changed",
                        {"state": CaseState.REJECTED.value,
                         "reason": validation.summary})
        else:  # need_more_info / không hội tụ
            _set_state(case_id, CaseState.NEEDS_INFO)
            await _emit(case_id, "orchestrator", "state_changed",
                        {"state": CaseState.NEEDS_INFO.value,
                         "reason": validation.summary,
                         "findings": validation.findings})
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        _set_state(case_id, CaseState.ESCALATED)
        await _emit(case_id, "orchestrator", "state_changed",
                    {"state": CaseState.ESCALATED.value, "reason": str(e)})


async def _execute_dag(case_id: str, plan: Plan
                       ) -> tuple[dict[str, Verdict], dict[str, Verdict]]:
    """Topo-sort + chạy song song các task không phụ thuộc nhau.
    Trả về (verdicts theo task_id, verdicts theo agent)."""
    verdicts: dict[str, Verdict] = {}          # theo task_id
    verdict_by_agent: dict[str, Verdict] = {}  # theo agent (cho validation)
    remaining = {t.task_id: t for t in plan.tasks}

    while remaining:
        ready = [t for t in remaining.values()
                 if all(d in verdicts for d in t.depends_on)]
        if not ready:
            raise RuntimeError("DAG bế tắc — dependency không thỏa")
        await _emit(case_id, "orchestrator", "tasks_dispatched",
                    {"parallel": [t.task_id for t in ready]})

        async def _run(t):
            params = dict(t.params)
            if t.agent == "validation":
                params["verdicts"] = {
                    a: v.model_dump(mode="json") for a, v in verdict_by_agent.items()
                }
            return t, await _dispatch(case_id, t.task_id, t.agent,
                                      {"objective": t.objective, "params": params})

        results = await asyncio.gather(*[_run(t) for t in ready])
        for t, v in results:
            verdicts[t.task_id] = v
            verdict_by_agent[t.agent] = v
            remaining.pop(t.task_id)
    return verdicts, verdict_by_agent


async def _build_package(case_id: str, plan: Plan, validation: Verdict) -> None:
    final_verdicts = [
        Verdict(**v) for v in validation.data.get("final_verdicts", {}).values()
    ]
    limit = validation.proposed_limit
    level = ("branch_director"
             if (limit or 0) <= config.BRANCH_APPROVAL_LIMIT else "head_office")
    package = ApprovalPackage(
        case_id=case_id, plan_version=plan.version,
        policy_version=config.POLICY_VERSION,
        recommendation=validation.data.get("narrative") or validation.summary,
        proposed_limit=limit,
        conditions=validation.conditions,
        verdicts=final_verdicts,
        trace_summary=[e.quote for e in validation.evidence],
        required_approver_level=level,
    ).model_dump(mode="json")

    import time as _t
    db.update_case(case_id, package=package,
                   sla_deadline=_t.time() + config.APPROVAL_SLA_SECONDS)
    _set_state(case_id, CaseState.PENDING_APPROVAL)
    await _emit(case_id, "orchestrator", "approval_package_ready",
                {"package": package,
                 "package_hash": approval.package_hash(package)})
    await _emit(case_id, "orchestrator", "state_changed",
                {"state": CaseState.PENDING_APPROVAL.value,
                 "required_approver_level": level})


async def approve_and_commit(case_id: str, approver: str) -> dict:
    """HITL phê duyệt -> phát token -> dispatch Operations pha COMMIT."""
    case = db.get_case(case_id)
    if not case or case["state"] != CaseState.PENDING_APPROVAL.value:
        return {"error": f"case không ở trạng thái Pending Approval"}
    package = case["package"]

    tok = approval.issue(case_id, package, approver)
    db.update_case(case_id, approver=approver)
    await _emit(case_id, "hitl", "approved",
                {"approver": approver, "token_expires_at": tok["expires_at"]})
    _set_state(case_id, CaseState.EXECUTING)
    await _emit(case_id, "orchestrator", "state_changed",
                {"state": CaseState.EXECUTING.value})

    plan = db.get_latest_plan(case_id) or {}
    verdict = await _dispatch(case_id, "t_commit", "operations", {
        "objective": "Thực thi tạo khoản vay sau phê duyệt",
        "params": {"phase": "commit", "approval_token": tok["token"],
                   "approved_limit": package.get("proposed_limit"),
                   "plan_version": package.get("plan_version", 1),
                   "request": case["payload"]["request"]},
    })

    if verdict.decision == VerdictDecision.PASS_:
        _set_state(case_id, CaseState.COMPLETED)
        await _emit(case_id, "orchestrator", "state_changed",
                    {"state": CaseState.COMPLETED.value,
                     "loan_id": verdict.data.get("loan_id")})
        return {"status": "completed", "loan_id": verdict.data.get("loan_id")}

    # Token vô hiệu / precondition fail -> re-plan có giới hạn; quá giới hạn -> Escalated
    stage = verdict.data.get("stage", "")
    await _emit(case_id, "operations", "commit_blocked",
                {"stage": stage, "summary": verdict.summary})
    if stage in ("token_verify", "precondition") and \
            case["replan_count"] < config.MAX_REPLAN_ROUNDS:
        db.update_case(case_id, replan_count=case["replan_count"] + 1)
        await _emit(case_id, "planner", "replan_triggered",
                    {"reason": verdict.summary,
                     "round": case["replan_count"] + 1})
        asyncio.create_task(run_analysis(case_id))
        return {"status": "replanning", "reason": verdict.summary}

    _set_state(case_id, CaseState.ESCALATED)
    await _emit(case_id, "orchestrator", "state_changed",
                {"state": CaseState.ESCALATED.value, "reason": verdict.summary})
    return {"status": "escalated", "reason": verdict.summary}


async def supplement_and_replan(case_id: str, documents: list[dict]) -> dict:
    """Chuyên viên bổ sung hồ sơ -> Document Agent -> re-plan (giới hạn số vòng)."""
    case = db.get_case(case_id)
    if not case:
        return {"error": "case không tồn tại"}
    if case["replan_count"] >= config.MAX_REPLAN_ROUNDS:
        _set_state(case_id, CaseState.ESCALATED)
        await _emit(case_id, "orchestrator", "state_changed",
                    {"state": CaseState.ESCALATED.value,
                     "reason": f"vượt giới hạn {config.MAX_REPLAN_ROUNDS} vòng re-plan"})
        return {"status": "escalated"}
    plan_raw = db.get_latest_plan(case_id)
    changed_inputs = {doc.get("doc_type", "document") for doc in documents}
    invalidated: set[str] = set()
    if plan_raw:
        try:
            invalidated = invalidated_tasks(Plan(**plan_raw), changed_inputs)
        except Exception:  # noqa: BLE001
            invalidated = set()
    payload = case["payload"]
    payload["documents"] = payload.get("documents", []) + documents
    db.update_case(case_id, payload=payload, replan_count=case["replan_count"] + 1)
    await _emit(case_id, "hitl", "documents_supplemented",
                {"count": len(documents)})
    await _emit(case_id, "planner", "replan_triggered",
                {"reason": "bổ sung hồ sơ", "round": case["replan_count"] + 1,
                 "invalidated_tasks": sorted(invalidated)})
    asyncio.create_task(run_analysis(case_id))
    return {"status": "replanning"}
