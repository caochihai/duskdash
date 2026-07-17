import unittest
from gateway.metrics import single_agent_baseline

class MetricsTests(unittest.TestCase):
    def test_baseline_has_no_commit_permission(self):
        result = single_agent_baseline({"case_id": "c", "payload": {"request": {"amount": 1}}})
        self.assertFalse(result["commit_permitted"])
        self.assertEqual(result["provider"], "deterministic_fake")
