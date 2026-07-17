from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable

from pydantic import BaseModel


class SideEffect(str, Enum):
    READ = "READ"
    DRAFT = "DRAFT"
    WRITE = "WRITE"


class ToolDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    result_model: type[BaseModel]
    allowed_agents: frozenset[str]
    side_effect: SideEffect
    handler: Callable[[BaseModel], Awaitable[BaseModel]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise ToolDenied(f"Unknown tool: {name}")
        return self._tools[name]

    def schemas_for(self, agent_id: str, phase: str) -> list[dict]:
        return [{"name": spec.name, "parameters": spec.args_model.model_json_schema()}
                for spec in self._tools.values() if agent_id in spec.allowed_agents
                and not (phase == "dry_run" and spec.side_effect == SideEffect.WRITE)]
