"""Wrapper LLM cho Engine — dùng để VIẾT VĂN XUÔI (summary/recommendation).

Nguyên tắc chống bịa nguồn: LLM KHÔNG bao giờ tạo citation. Provenance (citation +
bbox + kết quả SQL) do code tất định dựng; LLM chỉ diễn giải các claim đã có nguồn.

`LLM_PROVIDER=mock` (hoặc thiếu API key) → sinh văn xuôi tất định, không gọi mạng,
để Engine chạy trong container/CI mà không cần khoá API.
"""

from __future__ import annotations

from . import config


async def narrate(system: str, user: str) -> str:
    """Trả về một đoạn văn xuôi. Mock mode: ghép template tất định."""
    if config.use_mock_llm():
        return _mock_narrate(user)
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
            timeout=config.LLM_TIMEOUT,
        )
        resp = await client.chat.completions.create(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip() or _mock_narrate(user)
    except Exception:  # noqa: BLE001 - không để lỗi LLM làm sập deep-research
        return _mock_narrate(user)


def _mock_narrate(user: str) -> str:
    """Văn xuôi tất định: lấy các dòng '- ...' làm ý chính, không bịa nguồn mới."""
    bullets = [ln.strip("- ").strip() for ln in user.splitlines() if ln.strip().startswith("-")]
    if not bullets:
        head = user.strip().splitlines()[0] if user.strip() else ""
        return head[:300]
    lead = bullets[0]
    rest = "; ".join(bullets[1:4])
    if rest:
        return f"{lead}. Các điểm chính: {rest}."
    return f"{lead}."
