import unittest
from common.schemas import Plan, PlanTask
from gateway.replanning import invalidated_tasks

class ReplanningTests(unittest.TestCase):
    def test_only_affected_branch_and_downstream_is_invalidated(self):
        plan = Plan(case_id="c", tasks=[
            PlanTask(task_id="document", agent="document", objective="x", affects=["cccd"]),
            PlanTask(task_id="credit", agent="credit", objective="x", affects=["financials"]),
            PlanTask(task_id="compliance", agent="compliance", objective="x", depends_on=["document"]),
            PlanTask(task_id="operations", agent="operations", objective="x", depends_on=["credit", "compliance"]),
            PlanTask(task_id="validation", agent="validation", objective="x", depends_on=["operations"]),
        ])
        self.assertEqual(invalidated_tasks(plan, {"cccd"}), {"document", "compliance", "operations", "validation"})
