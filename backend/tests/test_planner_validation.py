import unittest
from common.schemas import Plan, PlanTask

AGENTS = {"credit", "compliance", "operations", "validation"}

class PlannerValidationTests(unittest.TestCase):
    def test_rejects_cycle_and_preapproval_commit(self):
        plan = Plan(case_id="c", tasks=[
            PlanTask(task_id="credit", agent="credit", objective="x", depends_on=["validation"]),
            PlanTask(task_id="compliance", agent="compliance", objective="x"),
            PlanTask(task_id="operations", agent="operations", objective="x", params={"phase": "commit"}),
            PlanTask(task_id="validation", agent="validation", objective="x", depends_on=["credit"]),
        ])
        errors = plan.validate_against_registry(AGENTS)
        self.assertTrue(any("chu trình" in error for error in errors))
        self.assertTrue(any("commit" in error for error in errors))
