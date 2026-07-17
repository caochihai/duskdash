import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "cases"

class FixtureTests(unittest.TestCase):
    def test_scenarios_are_synthetic_and_have_expected_outcomes(self):
        scenarios = [json.loads(path.read_text(encoding="utf-8")) for path in ROOT.glob("*.json")]
        self.assertEqual(len(scenarios), 3)
        self.assertTrue(all(item["scenario"] and item["expected"] for item in scenarios))
        self.assertTrue(all(item["case"]["request"]["business_id"].startswith("SYN-") for item in scenarios))
