import unittest

from agents.relevance_agent_v1 import RelevanceAgentV1
from agents.risk_agent_v1 import RiskAgentV1
from agents.risk_agent_v1_1 import RiskAgentV1_1
from benchmarks.metrics import ndcg_at_k, ndcg_at_k_legacy


class V1AgentParsingTests(unittest.TestCase):
    def test_relevance_parser_accepts_weighted_rubric(self):
        agent = RelevanceAgentV1.__new__(RelevanceAgentV1)
        result = agent._parse_response(
            '{"novelty": 20, "technical_relevance": 25, "applicability": 20, '
            '"timeliness": 15, "score": 80, "reasoning": "Useful release."}',
            {},
        )
        self.assertEqual(result["score"], 80)
        self.assertFalse(result["used_fallback"])

    def test_risk_parser_requires_explicit_category_and_boolean(self):
        agent = RiskAgentV1.__new__(RiskAgentV1)
        result = agent._parse_response(
            '{"risk_level":"MEDIUM","risk_category":"SUSPICION",'
            '"concerns":["Suspicious naming"],"evidence":["hack"],'
            '"breaking_changes":false}',
            {},
        )
        self.assertEqual(result["risk_category"], "SUSPICION")
        self.assertFalse(result["used_fallback"])

    def test_risk_fallback_does_not_promote_suspicion_to_high(self):
        agent = RiskAgentV1.__new__(RiskAgentV1)
        result = agent._fallback_assess({"title": "Roblox executor", "description": ""}, "test")
        self.assertEqual(result["risk_level"], "MEDIUM")
        self.assertEqual(result["risk_category"], "SUSPICION")

    def test_v11_promotes_explicit_eol_removal_to_compatibility(self):
        result = RiskAgentV1_1._apply_evidence_rules(
            {"title": "release", "description": "Remove EOL'd Python 3.10 from partner packages"},
            {"risk_level": "LOW", "risk_category": "NONE", "breaking_changes": False,
             "concerns": [], "evidence": []},
        )
        self.assertTrue(result["breaking_changes"])
        self.assertEqual(result["risk_category"], "COMPATIBILITY")
        self.assertEqual(result["evidence_strength"], "CONFIRMED")

    def test_v11_does_not_flag_negated_drop_as_breaking(self):
        result = RiskAgentV1_1._apply_evidence_rules(
            {"title": "release", "description": "Patch without dropping Python 3.10"},
            {"risk_level": "LOW", "risk_category": "NONE", "breaking_changes": False,
             "concerns": [], "evidence": []},
        )
        self.assertFalse(result["breaking_changes"])

    def test_v11_keeps_positive_marker_when_same_release_has_a_negative_example(self):
        result = RiskAgentV1_1._apply_evidence_rules(
            {"title": "release", "description": "Remove EOL'd Python 3.10. Patch without dropping Python 3.10."},
            {"risk_level": "LOW", "risk_category": "NONE", "breaking_changes": False,
             "concerns": [], "evidence": []},
        )
        self.assertTrue(result["breaking_changes"])

    def test_v11_removes_unsubstantiated_suspicion(self):
        result = RiskAgentV1_1._apply_evidence_rules(
            {"title": "Research paper", "description": "The model has a limitation."},
            {"risk_level": "MEDIUM", "risk_category": "SUSPICION", "breaking_changes": False,
             "concerns": ["Concern"], "evidence": ["Limitation"]},
        )
        self.assertEqual(result["risk_level"], "LOW")
        self.assertEqual(result["risk_category"], "NONE")
        self.assertEqual(result["evidence_strength"], "NONE")


class MetricDefinitionTests(unittest.TestCase):
    def test_normalized_ndcg_is_documented_and_bounded(self):
        value = ndcg_at_k([100, 0, 50], [50, 100, 0], 3)
        legacy = ndcg_at_k_legacy([100, 0, 50], [50, 100, 0], 3)
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)
        self.assertNotEqual(value, legacy)


if __name__ == "__main__":
    unittest.main()
