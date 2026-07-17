import unittest
from pydantic import BaseModel
from tools.registry import SideEffect, ToolDenied, ToolRegistry, ToolSpec
from tools.runner import ToolRunner

class Args(BaseModel): value: int
class Result(BaseModel): value: int
async def write(args): return {"value": args.value}

class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_is_denied_before_approval(self):
        registry = ToolRegistry(); registry.register(ToolSpec("commit", Args, Result, frozenset({"operations"}), SideEffect.WRITE, write))
        with self.assertRaises(ToolDenied):
            await ToolRunner(registry).execute(agent_id="operations", phase="dry_run", tool_name="commit", raw_args={"value": 1}, case_state="In Analysis")
