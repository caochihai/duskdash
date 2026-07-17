from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from common import config
from common.schemas import CaseState
from gateway import approval, db
from gateway.state_machine import InvalidStateTransition


class FoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = config.GATEWAY_DB
        config.GATEWAY_DB = Path(self.temp_dir.name) / "gateway.db"
        db.init()
        self.case_id = "case_test"
        db.create_case(
            self.case_id,
            {"request": {"business_id": "B001", "amount": 100}, "documents": []},
        )

    def tearDown(self) -> None:
        config.GATEWAY_DB = self.original_db
        self.temp_dir.cleanup()

    def _package(self) -> dict:
        return {
            "case_id": self.case_id,
            "plan_version": 1,
            "policy_version": config.POLICY_VERSION,
            "recommendation": "approve",
            "verdicts": [],
        }

    def test_case_state_transition_is_enforced(self) -> None:
        db.update_case(self.case_id, state=CaseState.IN_ANALYSIS.value)
        db.update_case(self.case_id, state=CaseState.PENDING_APPROVAL.value)
        with self.assertRaises(InvalidStateTransition):
            db.update_case(self.case_id, state=CaseState.COMPLETED.value)

    def test_events_are_pii_masked_before_persistence(self) -> None:
        event = db.add_event(
            self.case_id,
            "test",
            "test_event",
            {"id_number": "079088001234", "account": "123456789012"},
        )
        self.assertEqual(event["payload"]["id_number"], "***")
        self.assertNotIn("079088001234", str(db.get_events(self.case_id)))
        self.assertNotIn("123456789012", str(db.get_events(self.case_id)))
        self.assertTrue(db.verify_event_chain(self.case_id)["valid"])

    def test_approval_persists_only_hash_and_binds_plan_and_scope(self) -> None:
        db.update_case(self.case_id, state=CaseState.IN_ANALYSIS.value)
        package = self._package()
        db.update_case(self.case_id, package=package, state=CaseState.PENDING_APPROVAL.value)
        issued = approval.issue(self.case_id, package, "approver_1")

        with db._conn() as connection:  # noqa: SLF001 - verifies storage contract
            row = connection.execute("SELECT * FROM tokens").fetchone()
        self.assertNotIn(issued["token"], tuple(row))
        self.assertEqual(row["scope"], "commit")
        self.assertEqual(row["plan_version"], 1)

        self.assertFalse(approval.verify(self.case_id, issued["token"], scope="read")["valid"])
        self.assertTrue(approval.verify(self.case_id, issued["token"], scope="commit")["valid"])
        self.assertFalse(approval.verify(self.case_id, issued["token"], scope="commit")["valid"])


if __name__ == "__main__":
    unittest.main()
