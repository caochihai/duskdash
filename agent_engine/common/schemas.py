"""Các schema chuẩn của hệ thống: A2A envelope, Agent Card, Plan/DAG, Verdict.

Đây là "hợp đồng tích hợp" — mọi agent và gateway giao tiếp qua các model này.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------- A2A ----------
class MessageType(str, Enum):
    TASK_REQUEST = "task_request"
    TASK_RESULT = "task_result"
    INFO_REQUEST = "info_request"
    INFO_RESPONSE = "info_response"
    CHALLENGE = "challenge"
    CHALLENGE_RESPONSE = "challenge_response"
    ERROR = "error"


class Envelope(BaseModel):
    """Phong bì message A2A giữa các agent (và orchestrator)."""

    message_id: str = Field(default_factory=lambda: new_id("msg"))
    case_id: str
    task_id: Optional[str] = None
    from_agent: str
    to_agent: str
    type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    reply_to: Optional[str] = None
    ts: float = Field(default_factory=time.time)


class AgentSkill(BaseModel):
    id: str
    name: str
    description: str


class AgentCard(BaseModel):
    """Danh thiếp năng lực — Planner đọc registry các card này để sinh plan."""

    agent_id: str
    name: str
    description: str
    url: str
    skills: list[AgentSkill]
    version: str = "1.0"


# ---------- Plan / DAG ----------
class PlanTask(BaseModel):
    task_id: str
    agent: str  # agent_id trong registry
    objective: str
    depends_on: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    case_id: str
    version: int = 1
    rationale: str = ""
    tasks: list[PlanTask]

    def validate_against_registry(self, agent_ids: set[str]) -> list[str]:
        """Trả về danh sách lỗi; rỗng = hợp lệ."""
        errors = []
        ids = {t.task_id for t in self.tasks}
        if len(ids) != len(self.tasks):
            errors.append("task_id trùng lặp")
        for t in self.tasks:
            if t.agent not in agent_ids:
                errors.append(f"task {t.task_id}: agent '{t.agent}' không có trong registry")
            for d in t.depends_on:
                if d not in ids:
                    errors.append(f"task {t.task_id}: depends_on '{d}' không tồn tại")
        # kiểm tra chu trình bằng topo-sort đơn giản
        remaining = {t.task_id: set(t.depends_on) for t in self.tasks}
        while remaining:
            ready = [k for k, deps in remaining.items() if not deps]
            if not ready:
                errors.append("DAG có chu trình")
                break
            for k in ready:
                remaining.pop(k)
            for deps in remaining.values():
                deps.difference_update(ready)
        return errors


# ---------- Verdict ----------
class VerdictDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    NEED_MORE_INFO = "need_more_info"
    FLAG = "flag"
    PASS_ = "pass"  # dùng cho các check kỹ thuật (ops dry-run)


class Evidence(BaseModel):
    source: str  # tên tài liệu / tool
    quote: str  # trích dẫn hoặc dữ kiện


class Verdict(BaseModel):
    agent: str
    task_id: str
    decision: VerdictDecision
    summary: str
    confidence: float = 0.8
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    # trường chuyên biệt (tùy agent điền)
    proposed_limit: Optional[float] = None
    max_secured_limit: Optional[float] = None
    data: dict[str, Any] = Field(default_factory=dict)
    revision_of: Optional[str] = None  # đánh dấu verdict đã điều chỉnh sau challenge
    revision_reason: Optional[str] = None

    @classmethod
    def from_llm(cls, agent: str, task_id: str, result: dict) -> "Verdict":
        """Build Verdict an toàn từ output LLM — chuẩn hóa các kiểu model hay trả sai:
        evidence có thể là str/list[str]/list[dict]; findings/conditions có thể là str."""
        def _as_list(x) -> list:
            if x is None:
                return []
            return x if isinstance(x, list) else [x]

        def _to_evidence(x) -> list[Evidence]:
            out = []
            for e in _as_list(x):
                if isinstance(e, Evidence):
                    out.append(e)
                elif isinstance(e, dict):
                    out.append(Evidence(source=str(e.get("source", "llm")),
                                        quote=str(e.get("quote", e.get("text", e)))))
                elif isinstance(e, str) and e.strip():
                    out.append(Evidence(source="llm", quote=e))
            return out

        try:
            decision = VerdictDecision(str(result.get("decision", "need_more_info")).lower())
        except ValueError:
            decision = VerdictDecision.NEED_MORE_INFO
        return cls(
            agent=agent, task_id=task_id, decision=decision,
            summary=str(result.get("summary", "")),
            proposed_limit=result.get("proposed_limit"),
            max_secured_limit=result.get("max_secured_limit"),
            findings=[str(f) for f in _as_list(result.get("findings"))],
            conditions=[str(c) for c in _as_list(result.get("conditions"))],
            evidence=_to_evidence(result.get("evidence")),
        )


# ---------- Case ----------
class CaseState(str, Enum):
    DRAFT = "Draft"
    IN_ANALYSIS = "In Analysis"
    NEEDS_INFO = "Needs Info"
    PENDING_APPROVAL = "Pending Approval"
    ESCALATED = "Escalated"
    EXECUTING = "Executing"
    COMPLETED = "Completed"
    REJECTED = "Rejected"


class LoanRequest(BaseModel):
    business_id: str
    amount: float
    term_months: int
    purpose: str
    has_collateral: bool = False
    collateral_id: Optional[str] = None


class CaseCreate(BaseModel):
    request: LoanRequest
    submitted_by: str = "chuyen_vien_qhkh"
    documents: list[dict[str, Any]] = Field(default_factory=list)
    # documents: [{"doc_type": "dkkd"|"bctc"|"sao_ke"|"cccd"|"so_do",
    #             "image_path": "..."(LLM mode) | "extracted": {...}(đã trích xuất)}]


class ApprovalPackage(BaseModel):
    case_id: str
    plan_version: int
    policy_version: str
    recommendation: str
    proposed_limit: Optional[float] = None
    conditions: list[str] = Field(default_factory=list)
    verdicts: list[Verdict]
    trace_summary: list[str] = Field(default_factory=list)
    required_approver_level: str = "branch_director"
