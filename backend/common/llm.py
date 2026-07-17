"""Wrapper LLM: vòng lặp tool-calling (agentic loop) trên OpenAI-compatible API.

Endpoint mặc định: FPT AI Marketplace. Phân vai model theo agent:
  - PLANNER_MODEL (gpt-oss-120b): sinh Task DAG, cần reasoning + JSON
  - SPECIALIST_MODEL (Llama-3.3-70B): tool-calling loop của Credit/Compliance
  - VISION_MODEL (Qwen2.5-VL-7B): Document Agent đọc ảnh tài liệu
"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Optional

from . import config

ToolFn = Callable[..., Awaitable[Any]]


class ToolDef:
    def __init__(self, name: str, description: str, parameters: dict,
                 fn: Optional[ToolFn]):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.fn = fn

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _client():
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


def parse_json_loose(text: str) -> dict:
    """Parse JSON kể cả khi model bọc trong ```json ...``` hoặc kèm văn bản."""
    if not text:
        raise ValueError("nội dung rỗng")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
    raise ValueError(f"không tìm thấy JSON trong: {text[:200]}")


async def chat_json(system: str, user: str, schema_hint: str = "",
                    model: str | None = None) -> dict:
    """Một lượt gọi LLM trả về JSON (Planner). Thử json_object mode trước,
    provider/model không hỗ trợ thì fallback parse loose."""
    client = _client()
    model = model or config.PLANNER_MODEL
    messages = [
        {"role": "system",
         "content": system + ("\n\nJSON schema:\n" + schema_hint if schema_hint else "")
         + "\nChỉ trả về JSON, không giải thích."},
        {"role": "user", "content": user},
    ]
    try:
        resp = await client.chat.completions.create(
            model=model, temperature=config.LLM_TEMPERATURE,
            response_format={"type": "json_object"}, messages=messages)
        return parse_json_loose(resp.choices[0].message.content or "")
    except Exception:  # noqa: BLE001 - retry không có response_format
        resp = await client.chat.completions.create(
            model=model, temperature=config.LLM_TEMPERATURE, messages=messages)
        return parse_json_loose(resp.choices[0].message.content or "")


async def vision_extract(system: str, image_path: str, schema_hint: str) -> dict:
    """Trích xuất có cấu trúc từ ảnh tài liệu (Document Intelligence Agent)."""
    import base64
    from pathlib import Path

    data = base64.b64encode(Path(image_path).read_bytes()).decode()
    suffix = Path(image_path).suffix.lstrip(".").lower() or "png"
    if suffix == "jpg":
        suffix = "jpeg"
    client = _client()
    messages = [
        {"role": "system",
         "content": system + "\n\nJSON schema:\n" + schema_hint
         + "\nChỉ trả về JSON, không giải thích."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Trích xuất thông tin từ tài liệu này."},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/{suffix};base64,{data}"}},
            ],
        },
    ]
    resp = await client.chat.completions.create(
        model=config.VISION_MODEL, temperature=0, messages=messages)
    return parse_json_loose(resp.choices[0].message.content or "")


async def tool_loop(
    system: str,
    user: str,
    tools: list[ToolDef],
    submit_tool: str = "submit_verdict",
    max_iterations: int | None = None,
    model: str | None = None,
) -> dict:
    """Vòng lặp agentic: chạy đến khi LLM gọi submit_tool hoặc chạm giới hạn.

    Trả về arguments của submit_tool (dict). Nếu chạm giới hạn mà chưa submit,
    raise RuntimeError để tầng trên xử lý (escalate).
    """
    client = _client()
    model = model or config.SPECIALIST_MODEL
    max_iterations = max_iterations or config.LLM_MAX_TOOL_ITERATIONS
    tool_map = {t.name: t for t in tools}
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for i in range(max_iterations):
        # 2 vòng cuối: ép model BẮT BUỘC gọi submit_tool (chống lặp tool vô hạn)
        force_submit = i >= max_iterations - 2
        kwargs: dict = {"model": model, "temperature": config.LLM_TEMPERATURE,
                        "tools": [t.to_openai() for t in tools], "messages": messages}
        if force_submit:
            kwargs["tool_choice"] = {"type": "function",
                                     "function": {"name": submit_tool}}
            messages.append({"role": "user",
                             "content": f"Đã đủ thông tin. BẮT BUỘC gọi `{submit_tool}` ngay bây giờ."})
        try:
            resp = await client.chat.completions.create(**kwargs)
        except Exception:  # noqa: BLE001 - một số model từ chối tool_choice ép buộc
            kwargs.pop("tool_choice", None)
            resp = await client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            # LLM trả text (hoặc content rỗng ở reasoning model) -> nhắc submit
            messages.append({"role": "assistant", "content": msg.content or "(trống)"})
            messages.append(
                {"role": "user", "content": f"Hãy hoàn tất bằng cách gọi tool `{submit_tool}`."}
            )
            continue
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name,
                                  "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if tc.function.name == submit_tool:
                return args
            tool = tool_map.get(tc.function.name)
            if tool is None or tool.fn is None:
                result: Any = {"error": f"tool {tc.function.name} không tồn tại"}
            else:
                try:
                    result = await tool.fn(**args)
                except Exception as e:  # noqa: BLE001 - trả lỗi về cho LLM tự xử lý
                    result = {"error": str(e)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
    raise RuntimeError(f"LLM không submit sau {max_iterations} vòng tool-calling")
