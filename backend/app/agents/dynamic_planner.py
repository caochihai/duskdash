"""Dynamic Planner — thay thế create_plan() tĩnh bằng LLM sinh plan theo hồ sơ.

Cấy từ Agentic Core Engine (agent_engine/gateway/planner.py) vào contracts của
platform. Nguyên tắc giữ nguyên từ engine:
  - LLM đề xuất cấu trúc plan (chọn task, objective theo đặc điểm hồ sơ, dependency)
  - Validate chặt bằng schema + quy tắc bất biến (validation luôn sau chuyên gia,
    synthesis sau validation, report cuối cùng)
  - Sai/timeout -> FALLBACK plan tĩnh của AnalysisOrchestrator, ghi nhận source
    minh bạch ("llm" | "static_fallback")

Config qua env (không đụng Settings của platform để module này tự đứng được):
  FPT_API_KEY / LLM_API_KEY, LLM_BASE_URL (mặc định FPT Marketplace),
  PLANNER_MODEL (mặc định gpt-oss-120b — đã probe JSON mode OK).

Chưa được import ở đâu — seam tích hợp. Wire vào chỗ gọi
AnalysisOrchestrator.create_plan() khi team thống nhất.
"""
from __future__ import annotations

import json
import os
import re
from uuid import UUID, uuid5

from app.agents.orchestrator import (
    AnalysisOrchestrator,
    AnalysisPlan,
    AnalysisTaskPlan,
    TaskCode,
)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://mkp-api.fptcloud.com/v1")
LLM_API_KEY = os.getenv("FPT_API_KEY") or os.getenv("LLM_API_KEY", "")
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "gpt-oss-120b")

# Quy tắc bất biến của pipeline (bảo toàn ngữ nghĩa của orchestrator tĩnh)
_REQUIRED = {TaskCode.VALIDATION, TaskCode.SYNTHESIS, TaskCode.REPORT_GENERATION}
_EXPERT_CODES = {TaskCode.DOCUMENT_REVIEW, TaskCode.CREDIT_ASSESSMENT, TaskCode.POLICY_CHECK}
_AGENT_TYPE = {
    TaskCode.DOCUMENT_REVIEW: "DOCUMENT",
    TaskCode.CREDIT_ASSESSMENT: "CREDIT",
    TaskCode.POLICY_CHECK: "LEGAL_COMPLIANCE",
    TaskCode.VALIDATION: "VALIDATOR",
    TaskCode.SYNTHESIS: "SYNTHESIZER",
    TaskCode.REPORT_GENERATION: "REPORT_WRITER",
}

_SCHEMA_HINT = (
    '{"rationale": str, "tasks": [{"task_code": '
    '"DOCUMENT_REVIEW"|"CREDIT_ASSESSMENT"|"POLICY_CHECK"|"VALIDATION"|'
    '"SYNTHESIS"|"REPORT_GENERATION", "objective": str, '
    '"depends_on": ["TASK_CODE", ...]}]}'
)


def _parse_json_loose(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


async def _llm_propose(case_context: dict) -> dict:
    import httpx

    body = {
        "model": PLANNER_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "Bạn là Planner của hệ multi-agent thẩm định tín dụng. Sinh kế hoạch "
                "task theo đặc điểm hồ sơ (có/không tài liệu đính kèm, có/không TSĐB, "
                "ngành rủi ro, CIC). Quy tắc: VALIDATION phụ thuộc mọi task chuyên gia; "
                "SYNTHESIS phụ thuộc VALIDATION; REPORT_GENERATION phụ thuộc SYNTHESIS; "
                "chỉ tạo DOCUMENT_REVIEW nếu có tài liệu. Objective viết tiếng Việt, "
                "cụ thể theo hồ sơ. Chỉ trả về JSON.\nSchema:\n" + _SCHEMA_HINT
            )},
            {"role": "user", "content": f"Bối cảnh hồ sơ: {case_context}"},
        ],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json=body,
        )
        r.raise_for_status()
    return _parse_json_loose(r.json()["choices"][0]["message"]["content"] or "")


def _build_plan(analysis_case_id: UUID, proposal: dict) -> AnalysisPlan:
    """Validate đề xuất của LLM và dựng AnalysisPlan đúng contract frozen."""
    raw_tasks = proposal.get("tasks", [])
    codes: list[TaskCode] = []
    by_code: dict[TaskCode, dict] = {}
    for t in raw_tasks:
        code = TaskCode(t["task_code"])  # ValueError nếu code lạ -> fallback
        if code in by_code:
            raise ValueError(f"task_code trùng: {code}")
        by_code[code] = t
        codes.append(code)

    missing = _REQUIRED - set(codes)
    if missing:
        raise ValueError(f"thiếu task bắt buộc: {missing}")
    experts = [c for c in codes if c in _EXPERT_CODES]
    if not experts:
        raise ValueError("plan không có task chuyên gia nào")

    # Ép bất biến dependency bất kể LLM đề xuất gì (an toàn > sáng tạo)
    task_ids = {c: uuid5(analysis_case_id, c.value) for c in codes}
    deps: dict[TaskCode, tuple[UUID, ...]] = {}
    for c in experts:
        deps[c] = (
            (task_ids[TaskCode.DOCUMENT_REVIEW],)
            if TaskCode.DOCUMENT_REVIEW in task_ids and c != TaskCode.DOCUMENT_REVIEW
            else ()
        )
    deps[TaskCode.VALIDATION] = tuple(task_ids[c] for c in experts)
    deps[TaskCode.SYNTHESIS] = (task_ids[TaskCode.VALIDATION],)
    deps[TaskCode.REPORT_GENERATION] = (task_ids[TaskCode.SYNTHESIS],)

    tasks = tuple(
        AnalysisTaskPlan(
            id=task_ids[c],
            task_code=c,
            agent_type=_AGENT_TYPE[c],
            objective=str(by_code[c].get("objective") or c.value),
            depends_on=deps.get(c, ()),
        )
        for c in codes
    )
    return AnalysisPlan(analysis_case_id=analysis_case_id, tasks=tasks)


async def create_dynamic_plan(
    orchestrator: AnalysisOrchestrator,
    analysis_case_id: UUID,
    case_context: dict,
) -> tuple[AnalysisPlan, str]:
    """Trả về (plan, source). source: 'llm' | 'static_fallback'.

    case_context ví dụ: {"has_documents": true, "has_collateral": false,
    "industry_risk": "high", "cic_group": 2, "amount": 5e9}
    """
    if LLM_API_KEY:
        for _ in range(2):  # tối đa 2 lần thử trước khi fallback
            try:
                proposal = await _llm_propose(case_context)
                return _build_plan(analysis_case_id, proposal), "llm"
            except Exception:  # noqa: BLE001 - mọi lỗi đều rơi về fallback an toàn
                continue
    return orchestrator.create_plan(analysis_case_id), "static_fallback"
