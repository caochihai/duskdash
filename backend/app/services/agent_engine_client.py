"""Client gọi Agentic Core Engine (agent_engine/) từ platform backend.

Engine là hệ multi-agent độc lập (gateway :8000 riêng của engine) cung cấp:
  - Planner LLM sinh Task DAG động + re-plan có giới hạn
  - 5 specialist agent chạy như A2A service độc lập (document/credit/compliance/
    operations/validation) với challenge loop máy-tự-giải
  - MCP layer: mọi tool call đi qua MCP server, audit tập trung
  - OCR thật (FPT gemma-4-31B-it, benchmark CER 0.004 / Numeric Acc 97%)
  - Commit an toàn: approval token (hash package + policy version + expiry),
    TOCTOU precondition re-check, idempotency key, đối soát in-doubt + retry 1 lần

Cách dùng dự kiến trong multi_agent_analysis_service / analysis worker:

    client = AgentEngineClient()
    case_id = await client.create_case(request=..., documents=[...])
    await client.run(case_id)
    state = await client.wait_final(case_id)
    package = (await client.get_case(case_id)).get("package")

Chưa được import ở đâu — đây là seam tích hợp, không ảnh hưởng code hiện có.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

DEFAULT_ENGINE_URL = os.getenv("AGENT_ENGINE_URL", "http://127.0.0.1:8010")

_FINAL_STATES = {"Pending Approval", "Needs Info", "Rejected", "Escalated", "Completed"}


class AgentEngineClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        self._base = (base_url or DEFAULT_ENGINE_URL).rstrip("/")
        self._timeout = timeout

    async def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=self._timeout)

    async def create_case(
        self,
        request: dict[str, Any],
        documents: list[dict[str, Any]] | None = None,
        submitted_by: str = "platform",
    ) -> str:
        async with await self._client() as c:
            r = await c.post("/cases", json={
                "request": request,
                "documents": documents or [],
                "submitted_by": submitted_by,
            })
            r.raise_for_status()
            return r.json()["case_id"]

    async def run(self, case_id: str) -> None:
        async with await self._client() as c:
            (await c.post(f"/cases/{case_id}/run")).raise_for_status()

    async def get_case(self, case_id: str) -> dict[str, Any]:
        async with await self._client() as c:
            r = await c.get(f"/cases/{case_id}")
            r.raise_for_status()
            return r.json()

    async def get_events(self, case_id: str, after: int = 0) -> list[dict[str, Any]]:
        """Trace đầy đủ cho dashboard: plan DAG, task status, A2A message, verdict."""
        async with await self._client() as c:
            r = await c.get(f"/cases/{case_id}/events", params={"after": after})
            r.raise_for_status()
            return r.json()

    async def wait_final(self, case_id: str, timeout_s: float = 600) -> str:
        for _ in range(int(timeout_s)):
            state = (await self.get_case(case_id)).get("state", "")
            if state in _FINAL_STATES:
                return state
            await asyncio.sleep(1)
        raise TimeoutError(f"case {case_id} chưa đạt trạng thái cuối sau {timeout_s}s")

    async def approve(self, case_id: str, approver: str,
                      approver_level: str = "branch_director") -> dict[str, Any]:
        """HITL phê duyệt -> engine phát approval token và thực thi commit an toàn."""
        async with await self._client() as c:
            r = await c.post(f"/cases/{case_id}/approve",
                             json={"approver": approver, "approver_level": approver_level})
            r.raise_for_status()
            return r.json()

    async def agent_registry(self) -> list[dict[str, Any]]:
        """Agent Cards của các chuyên gia đang online (A2A discovery)."""
        async with await self._client() as c:
            r = await c.get("/agents")
            r.raise_for_status()
            return r.json()
