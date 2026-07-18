"""Client MCP: mọi agent gọi tool nghiệp vụ qua đây — không import trực tiếp.

Mỗi call mở một session streamable-http (local nên chi phí không đáng kể).
"""
from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from . import config


async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    async with streamablehttp_client(config.MCP_CORE_BANKING_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments or {})
    if result.structuredContent is not None:
        sc = result.structuredContent
        # FastMCP bọc giá trị trả về đơn trong {"result": ...}
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    texts = [c.text for c in result.content if getattr(c, "text", None)]
    raw = "\n".join(texts)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def list_tools() -> list[dict]:
    async with streamablehttp_client(config.MCP_CORE_BANKING_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.list_tools()
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
        for t in res.tools
    ]
