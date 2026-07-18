"""Planner: đọc Agent Card registry, sinh Task DAG động theo đặc điểm hồ sơ.

LLM mode: LLM sinh plan JSON, validate schema + registry, sai 2 lần -> fallback
template (ghi event fallback để minh bạch).
Rules mode: template có điều kiện — cùng logic nhánh mà LLM được yêu cầu học theo.
"""
from __future__ import annotations

import httpx

from common import config, llm, mcp_client
from common.schemas import AgentCard, Plan, PlanTask

_registry_cache: dict[str, AgentCard] = {}


async def get_registry() -> dict[str, AgentCard]:
    """Discovery: đọc agent card của mọi agent đang online."""
    if _registry_cache:
        return _registry_cache
    async with httpx.AsyncClient(timeout=5) as client:
        for name in config.AGENT_PORTS:
            try:
                resp = await client.get(
                    f"{config.agent_url(name)}/.well-known/agent-card.json")
                _registry_cache[name] = AgentCard(**resp.json())
            except Exception:  # noqa: BLE001 - agent offline thì bỏ qua khỏi registry
                continue
    return _registry_cache


def _template_plan(case_id: str, payload: dict, context: dict, version: int) -> Plan:
    """Template có điều kiện — nhánh theo đặc điểm hồ sơ (baseline cho LLM)."""
    request = payload["request"]
    documents = payload.get("documents", [])
    has_docs = bool(documents)
    has_collateral = bool(request.get("has_collateral"))
    industry_risk = context.get("industry_risk", "normal")
    cic_group = context.get("cic_group", 1)

    tasks: list[PlanTask] = []
    doc_dep: list[str] = []
    if has_docs:
        tasks.append(PlanTask(
            task_id="t_doc", agent="document",
            objective="Trích xuất và đối chiếu chéo bộ hồ sơ tài liệu",
            params={"documents": documents, "request": request}))
        doc_dep = ["t_doc"]

    credit_obj = "Thẩm định năng lực tài chính, đề xuất hạn mức"
    if cic_group >= 2:
        credit_obj += "; phân tích sâu lịch sử nợ nhóm 2 và nguồn trả nợ"
    tasks.append(PlanTask(task_id="t_credit", agent="credit", objective=credit_obj,
                          depends_on=doc_dep, params={"request": request}))

    comp_obj = "Kiểm tra KYB, AML/blacklist, CIC"
    if has_collateral:
        comp_obj += "; thẩm định pháp lý TSĐB và giới hạn LTV"
    if industry_risk == "high":
        comp_obj += "; đánh giá ngành rủi ro cao theo khẩu vị rủi ro"
    tasks.append(PlanTask(
        task_id="t_compliance", agent="compliance", objective=comp_obj,
        depends_on=doc_dep,
        params={"request": request, "check_collateral": has_collateral}))

    tasks.append(PlanTask(
        task_id="t_ops", agent="operations",
        objective="Kiểm tra điều kiện vận hành, tạo bản nháp hồ sơ vay (dry-run)",
        depends_on=["t_credit", "t_compliance"],
        params={"request": request, "phase": "dry_run"}))

    tasks.append(PlanTask(
        task_id="t_validation", agent="validation",
        objective="Xác thực chéo các kết luận, điều phối challenge, tổng hợp khuyến nghị",
        depends_on=["t_doc", "t_credit", "t_compliance", "t_ops"] if has_docs
        else ["t_credit", "t_compliance", "t_ops"],
        params={"request": request}))

    rationale = (
        f"Hồ sơ {'có' if has_collateral else 'không có'} TSĐB, "
        f"ngành rủi ro {industry_risk}, CIC nhóm {cic_group}, "
        f"{'kèm' if has_docs else 'không kèm'} tài liệu đính kèm "
        f"-> DAG {len(tasks)} task."
    )
    return Plan(case_id=case_id, version=version, rationale=rationale, tasks=tasks)


async def _llm_plan(case_id: str, payload: dict, context: dict, version: int,
                    registry: dict[str, AgentCard]) -> Plan | None:
    cards = "\n".join(
        f"- {c.agent_id}: {c.description} | skills: "
        + ", ".join(s.name for s in c.skills)
        for c in registry.values()
    )
    schema = ('{"rationale": str, "tasks": [{"task_id": str, "agent": str, '
              '"objective": str, "depends_on": [str], "params": {}}]}')
    for _ in range(2):
        try:
            data = await llm.chat_json(
                system="Bạn là Planner của hệ thống multi-agent thẩm định tín dụng SME. "
                       "Phân rã yêu cầu thành Task DAG, chỉ giao việc cho các agent sau:\n"
                       f"{cards}\n"
                       "Quy tắc: task validation luôn cuối cùng và phụ thuộc mọi task khác; "
                       "operations dry-run phụ thuộc credit + compliance; "
                       "chỉ tạo task document nếu có tài liệu đính kèm; "
                       "điều chỉnh objective theo đặc điểm hồ sơ (TSĐB, ngành, CIC). "
                       "Mỗi task phải có params.request = request gốc.",
                user=f"Hồ sơ: {payload}\nBối cảnh: {context}",
                schema_hint=schema,
            )
            plan = Plan(case_id=case_id, version=version,
                        rationale=data.get("rationale", ""),
                        tasks=[PlanTask(**t) for t in data["tasks"]])
            errors = plan.validate_against_registry(set(registry.keys()))
            if not errors:
                # đảm bảo params tối thiểu cho mỗi task
                for t in plan.tasks:
                    t.params.setdefault("request", payload["request"])
                    if t.agent == "document":
                        t.params.setdefault("documents", payload.get("documents", []))
                    if t.agent == "operations":
                        t.params.setdefault("phase", "dry_run")
                return plan
        except Exception:  # noqa: BLE001
            continue
    return None


async def make_plan(case_id: str, payload: dict, version: int) -> tuple[Plan, str]:
    """Trả về (plan, source) — source: 'llm' | 'template'."""
    registry = await get_registry()
    # Bối cảnh cho nhánh động: planner tự tra cứu đặc điểm hồ sơ qua MCP
    context: dict = {}
    try:
        biz = await mcp_client.call_tool(
            "get_business", {"business_id": payload["request"]["business_id"]})
        cic = await mcp_client.call_tool(
            "get_cic_status", {"business_id": payload["request"]["business_id"]})
        context = {"industry_risk": biz.get("industry_risk", "normal"),
                   "industry": biz.get("industry"),
                   "cic_group": cic.get("cic_group", 1),
                   "is_existing_customer": bool(biz.get("is_existing_customer"))}
    except Exception:  # noqa: BLE001
        pass

    # Planner dùng LLM ở cả hybrid và llm mode (đây là chỗ autonomy toả sáng)
    if config.LLM_MODE in ("llm", "hybrid"):
        plan = await _llm_plan(case_id, payload, context, version, registry)
        if plan is not None:
            return plan, "llm"
        # fallback minh bạch — vẫn chạy được demo
        return _template_plan(case_id, payload, context, version), "template_fallback"
    return _template_plan(case_id, payload, context, version), "template"
