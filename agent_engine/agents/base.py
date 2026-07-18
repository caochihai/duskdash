"""Agent base: biến mỗi specialist agent thành một service A2A độc lập.

Mỗi agent:
  - GET /.well-known/agent-card.json  -> Agent Card (Planner đọc registry từ đây)
  - POST /a2a                          -> nhận Envelope, dispatch theo MessageType
  - gọi tool nghiệp vụ qua MCP, tri thức qua RAG, nói chuyện với agent khác qua A2A
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Awaitable, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from common import config, events  # noqa: E402
from common.schemas import AgentCard, Envelope, MessageType, Verdict  # noqa: E402

TaskHandler = Callable[[Envelope], Awaitable[Verdict]]
InfoHandler = Callable[[Envelope], Awaitable[dict]]


async def a2a_send(from_agent: str, to_agent: str, env: Envelope) -> Envelope:
    """Gửi envelope trực tiếp tới agent khác (collaboration agent<->agent)."""
    url = f"{config.agent_url(to_agent)}/a2a"
    await events.emit(
        env.case_id, from_agent, f"a2a_{env.type.value}",
        {"to": to_agent, "task_id": env.task_id, "payload": env.payload},
    )
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=env.model_dump(mode="json"))
        resp.raise_for_status()
    return Envelope(**resp.json())


def build_agent_app(
    card: AgentCard,
    handle_task: TaskHandler,
    handle_challenge: Optional[TaskHandler] = None,
    handle_info: Optional[InfoHandler] = None,
) -> FastAPI:
    app = FastAPI(title=card.name)

    @app.get("/.well-known/agent-card.json")
    async def agent_card() -> dict:
        return card.model_dump()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "agent": card.agent_id}

    @app.post("/a2a")
    async def a2a_endpoint(env: Envelope) -> dict:
        try:
            if env.type == MessageType.TASK_REQUEST:
                await events.emit(env.case_id, card.agent_id, "task_started",
                                  {"task_id": env.task_id, "objective": env.payload.get("objective", "")})
                verdict = await handle_task(env)
                await events.emit(env.case_id, card.agent_id, "task_finished",
                                  {"task_id": env.task_id, "verdict": verdict.model_dump(mode="json")})
                reply_type = MessageType.TASK_RESULT
                payload = {"verdict": verdict.model_dump(mode="json")}
            elif env.type == MessageType.CHALLENGE:
                handler = handle_challenge or handle_task
                verdict = await handler(env)
                await events.emit(env.case_id, card.agent_id, "challenge_handled",
                                  {"task_id": env.task_id, "verdict": verdict.model_dump(mode="json")})
                reply_type = MessageType.CHALLENGE_RESPONSE
                payload = {"verdict": verdict.model_dump(mode="json")}
            elif env.type == MessageType.INFO_REQUEST and handle_info:
                info = await handle_info(env)
                reply_type = MessageType.INFO_RESPONSE
                payload = info
            else:
                reply_type = MessageType.ERROR
                payload = {"error": f"{card.agent_id} không xử lý message type {env.type}"}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            await events.emit(env.case_id, card.agent_id, "agent_error",
                              {"task_id": env.task_id, "error": str(e)})
            reply_type = MessageType.ERROR
            payload = {"error": str(e)}

        return Envelope(
            case_id=env.case_id, task_id=env.task_id,
            from_agent=card.agent_id, to_agent=env.from_agent,
            type=reply_type, payload=payload, reply_to=env.message_id,
        ).model_dump(mode="json")

    return app
