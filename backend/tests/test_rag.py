from __future__ import annotations

import unittest
from datetime import date

from common import rag


class RAGTests(unittest.TestCase):
    def test_returns_versioned_citation_for_effective_policy(self) -> None:
        hits = rag.search("credit", "DSCR tối thiểu", as_of=date(2026, 7, 1))
        self.assertTrue(hits)
        self.assertEqual(hits[0]["version"], "2026.07")
        self.assertIn("section", rag.citation(hits[0]))

    def test_rejects_policy_before_its_effective_date(self) -> None:
        self.assertEqual(rag.search("credit", "DSCR", as_of=date(2025, 12, 31)), [])

    def test_policy_content_is_marked_as_untrusted(self) -> None:
        self.assertIn("untrusted_content_flag", rag.search("credit", "DSCR")[0])
