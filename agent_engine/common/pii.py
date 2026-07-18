"""Che PII trước khi ghi event/log — số CCCD, số tài khoản, SĐT."""
from __future__ import annotations

import re
from typing import Any

_PATTERNS = [
    (re.compile(r"\b(\d{3})\d{6}(\d{3})\b"), r"\1******\2"),  # CCCD 12 số
    (re.compile(r"\b(\d{2})\d{5,8}(\d{2})\b"), r"\1*****\2"),  # số TK/SĐT
]

_SENSITIVE_KEYS = {"cccd", "id_number", "account_number", "phone", "so_cccd", "so_tai_khoan"}


def mask_text(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def mask(obj: Any) -> Any:
    """Đệ quy che PII trong dict/list/str."""
    if isinstance(obj, dict):
        return {
            k: ("***" if k.lower() in _SENSITIVE_KEYS and isinstance(v, str) and v else mask(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [mask(x) for x in obj]
    if isinstance(obj, str):
        return mask_text(obj)
    return obj
