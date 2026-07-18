"""Load only explicitly versioned local prompt files."""

from __future__ import annotations

import re
from pathlib import Path

_PROMPT_NAME = re.compile(r"^system-prompt\.v[1-9][0-9]*\.md$")


def load_system_prompt(agent_directory: str, version: int = 1) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9-]*", agent_directory) or version < 1:
        raise ValueError("invalid prompt identifier")
    filename = f"system-prompt.v{version}.md"
    if not _PROMPT_NAME.fullmatch(filename):
        raise ValueError("prompt filename must be explicitly versioned")
    path = Path(__file__).resolve().parent / agent_directory / filename
    return path.read_text(encoding="utf-8")
