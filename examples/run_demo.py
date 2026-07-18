"""Run one synthetic Credit Agent task and print the V1 result as JSON."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from credit_agent.agent import CreditAgent
from credit_agent.demo_tools import DemoCreditTools
from credit_agent.models import AgentConfig, CreditTaskInputV1


async def main() -> None:
    payload_path = Path(__file__).with_name("credit_task.json")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    task = CreditTaskInputV1.model_validate(payload)
    result = await CreditAgent(
        tools=DemoCreditTools(),
        config=AgentConfig(allow_placeholder_policy=True),
    ).run(task)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
