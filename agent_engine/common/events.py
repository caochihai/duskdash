"""Phát event về gateway — nguồn dữ liệu duy nhất cho dashboard trace/audit."""
from __future__ import annotations

from typing import Any

import httpx

from . import config, pii


async def emit(case_id: str, agent: str, etype: str, payload: dict[str, Any] | None = None):
    """Fire-and-forget: agent không được chết vì dashboard lỗi."""
    body = {
        "case_id": case_id,
        "agent": agent,
        "type": etype,
        "payload": pii.mask(payload or {}),
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(f"{config.GATEWAY_URL}/internal/events", json=body)
    except Exception:  # noqa: BLE001
        pass
