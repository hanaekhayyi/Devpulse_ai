"""Deterministic compatibility/suspicion markers (agents/v2/profiler.py) and metric definitions."""

import unittest

from agents.v2.profiler import SUSPICION_PATTERN, has_explicit_breaking_marker
from benchmarks.metrics import ndcg_at_k, ndcg_at_k_legacy


class MarkerTests(unittest.TestCase):
    def test_explicit_eol_removal_is_a_breaking_marker(self):
        self.assertTrue(has_explicit_breaking_marker("Remove EOL'd Python 3.10 from partner packages"))

    def test_negated_drop_is_not_breaking(self):
        self.assertFalse(has_explicit_breaking_marker("Patch without dropping Python 3.10"))

    def test_positive_marker_survives_a_negative_example(self):
        self.assertTrue(has_explicit_breaking_marker("Remove EOL'd Python 3.10. Patch without dropping Python 3.10."))

    def test_negated_breaking_change_is_ignored(self):
        self.assertFalse(has_explicit_breaking_marker("Bug fixes, no breaking changes."))

    def test_suspicion_vocabulary(self):
        self.assertTrue(SUSPICION_PATTERN.search("Roblox executor with keygen"))
        self.assertFalse(SUSPICION_PATTERN.search("The model has a limitation."))


class MetricDefinitionTests(unittest.TestCase):
    def test_normalized_ndcg_is_documented_and_bounded(self):
        value = ndcg_at_k([100, 0, 50], [50, 100, 0], 3)
        legacy = ndcg_at_k_legacy([100, 0, 50], [50, 100, 0], 3)
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)
        self.assertNotEqual(value, legacy)


if __name__ == "__main__":
    unittest.main()
