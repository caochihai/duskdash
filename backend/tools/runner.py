from __future__ import annotations

from .registry import SideEffect, ToolDenied, ToolRegistry


class ToolRunner:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(self, *, agent_id: str, phase: str, tool_name: str, raw_args: dict,
                      case_state: str, approval_valid: bool = False):
        spec = self.registry.get(tool_name)
        if agent_id not in spec.allowed_agents:
            raise ToolDenied(f"{agent_id} is not allowed to call {tool_name}")
        if spec.side_effect == SideEffect.WRITE:
            if phase != "commit":
                raise ToolDenied("WRITE tools are only allowed in commit phase")
            if case_state not in {"Executing", "Approved"} or not approval_valid:
                raise ToolDenied("Commit requires approved case and valid approval token")
        args = spec.args_model.model_validate(raw_args)
        return spec.result_model.model_validate(await spec.handler(args))
