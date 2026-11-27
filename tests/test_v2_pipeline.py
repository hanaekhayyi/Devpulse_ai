"""Offline tests for bloc 3: triage, verified synthesis, Agno workflow, main CLI."""

import unittest
from types import SimpleNamespace

from agents.v2.ratelimit import RateLimiter
from agents.v2.runner import StructuredLLM
from agents.v2.synthesis import DigestLLM, SynthesisAgentV2, deterministic_recommendations, verify_digest
from agents.v2.triage import fast_path_risk, needs_llm_risk
from main import parse_args
from pipeline.workflow import build_workflow, run_workflow

PAPER = {"source": "arxiv", "id": "p1", "title": "A paper on retrieval", "description": "We study RAG.", "metadata": {}}
SECURITY_PAPER = {"source": "arxiv", "id": "p2", "title": "Exploit found", "description": "CVE-2026-1234 in a parser.",
                  "metadata": {}}
REPO = {"source": "github", "id": "r1", "title": "org/tool", "description": "A tool.", "metadata": {}}


def assessed(sid, source, title, relevance, level="LOW", category="NONE", breaking=False):
    return {"id": sid, "source": source, "title": title, "description": "d",
            "relevance": {"score": relevance, "reasoning": "r"},
            "risk": {"risk_level": level, "risk_category": category, "breaking_changes": breaking}}


SIGNALS = [
    assessed("a", "github_releases", "lib v2.0", 80, "MEDIUM", "COMPATIBILITY", True),
    assessed("b", "github", "org/cheat-menu", 5, "MEDIUM", "SUSPICION"),
    assessed("c", "arxiv", "Paper 3", 72),
    assessed("d", "medium", "Blog", 20),
]


class FakeAgent:
    def __init__(self, content):
        self.content = content

    def run(self, prompt, stream=False):
        return SimpleNamespace(content=self.content, status="completed",
                               metrics=SimpleNamespace(input_tokens=1, output_tokens=1, cost=0))


def synthesis_with(content):
    agent = SynthesisAgentV2.__new__(SynthesisAgentV2)
    agent.use_llm = True
    agent.llm = StructuredLLM(name="t", instructions=["x"], schema=DigestLLM, model_id="fake", prompt_version="t",
                              agent_factory=lambda **_: FakeAgent(content), sleep=lambda _s: None,
                              limiter=RateLimiter(0), max_attempts=1)
    return agent


class TriageTests(unittest.TestCase):
    def test_plain_paper_takes_fast_path(self):
        self.assertFalse(needs_llm_risk(PAPER))

    def test_marker_forces_llm(self):
        self.assertTrue(needs_llm_risk(SECURITY_PAPER))

    def test_artifacts_always_go_to_llm(self):
        self.assertTrue(needs_llm_risk(REPO))

    def test_fast_path_has_risk_agent_shape(self):
        result = fast_path_risk(PAPER)
        self.assertEqual((result["risk_level"], result["risk_category"]), ("LOW", "NONE"))
        self.assertTrue(result["triaged"])
        self.assertFalse(result["used_fallback"])


class SynthesisTests(unittest.TestCase):
    def test_unknown_ids_are_rejected(self):
        out = DigestLLM(
            executive_summary="Analyzed 4 signals.",
            key_signals=[{"signal_id": "github_releases:a", "why_it_matters": "breaking"},
                         {"signal_id": "github:invented", "why_it_matters": "x"}],
            recommendations=[{"action": "Upgrade carefully", "signal_ids": ["github_releases:a", "x:y"]}],
        )
        by_id = {"github_releases:a": SIGNALS[0]}
        verified = verify_digest(out, by_id, {"total_signals": 4})
        self.assertEqual([k["signal_id"] for k in verified["key_signals"]], ["github_releases:a"])
        self.assertEqual(verified["recommendations"][0]["signal_ids"], ["github_releases:a"])
        self.assertEqual(set(verified["rejected_ids"]), {"github:invented", "x:y"})

    def test_invented_number_replaces_summary(self):
        out = DigestLLM(executive_summary="We analyzed 1000 signals.", key_signals=[], recommendations=[])
        verified = verify_digest(out, {}, {"total_signals": 4})
        self.assertTrue(verified["summary_replaced"])
        self.assertIsNone(verified["summary"])

    def test_llm_digest_is_used_when_verifiable(self):
        agent = synthesis_with({
            "executive_summary": "Analyzed 4 signals; one release breaks compatibility.",
            "key_signals": [{"signal_id": "github_releases:a", "why_it_matters": "Breaking change."}],
            "recommendations": [{"action": "Pin lib before upgrading", "signal_ids": ["github_releases:a"]}],
        })
        digest = agent.synthesize(SIGNALS)
        self.assertEqual(digest["synthesis"]["mode"], "llm")
        self.assertEqual(digest["facts"]["breaking_changes"], 1)
        self.assertIn("Analyzed 4 signals", digest["executive_summary"])

    def test_falls_back_when_nothing_verifiable(self):
        agent = synthesis_with({"executive_summary": "x", "key_signals": [{"signal_id": "nope", "why_it_matters": "y"}],
                                "recommendations": []})
        digest = agent.synthesize(SIGNALS)
        self.assertEqual(digest["synthesis"]["mode"], "deterministic")
        self.assertTrue(digest["synthesis"]["used_fallback"])

    def test_invalid_llm_answer_falls_back(self):
        digest = synthesis_with("not json").synthesize(SIGNALS)
        self.assertTrue(digest["synthesis"]["used_fallback"])
        self.assertTrue(digest["recommendations"])

    def test_high_risk_is_not_called_critical(self):
        recs = deterministic_recommendations([assessed("h", "github", "x", 50, "HIGH", "SECURITY")])
        actions = " ".join(r["action"] for r in recs)
        self.assertIn("high-risk", actions)
        self.assertNotIn("critical", actions)


class Rel:
    def score(self, s):
        return {"score": 60, "reasoning": "r", "used_fallback": False}


class Risk:
    def __init__(self):
        self.calls = 0

    def assess(self, s):
        self.calls += 1
        return {"risk_level": "LOW", "risk_category": "NONE", "breaking_changes": False, "used_fallback": False}


def collect(_limit):
    return [PAPER, SECURITY_PAPER, REPO]


class WorkflowTests(unittest.TestCase):
    def run_flow(self, llm_synthesis):
        risk = Risk()
        synth = synthesis_with({"executive_summary": "Analyzed 3 signals.",
                                "key_signals": [{"signal_id": "github:r1", "why_it_matters": "tool"}],
                                "recommendations": [{"action": "Try it", "signal_ids": ["github:r1"]}]})
        state = run_workflow(build_workflow(Rel(), risk, synth, collect_live=collect),
                             llm_synthesis=llm_synthesis, concurrency=2)
        return state, risk

    def test_triage_routes_only_needed_signals_to_llm(self):
        state, risk = self.run_flow(llm_synthesis=False)
        self.assertEqual(sorted(state["triage"]["risk_fast_path"]), ["arxiv:p1"])
        self.assertEqual(risk.calls, 2)
        self.assertEqual(len(state["assessed"]), 3)

    def test_router_selects_deterministic_synthesis(self):
        state, _ = self.run_flow(llm_synthesis=False)
        self.assertEqual(state["digest"]["synthesis"]["mode"], "deterministic")

    def test_router_selects_llm_synthesis(self):
        state, _ = self.run_flow(llm_synthesis=True)
        self.assertEqual(state["digest"]["synthesis"]["mode"], "llm")

    def test_condition_handles_empty_collection(self):
        state = run_workflow(build_workflow(Rel(), Risk(), synthesis_with("x"), collect_live=lambda _l: []),
                             llm_synthesis=True)
        self.assertEqual(state["digest"]["synthesis"]["mode"], "empty")


class CliTests(unittest.TestCase):
    def test_default_version_is_v2(self):
        self.assertEqual(parse_args([]).agent_version, "v2")

    def test_legacy_versions_selectable(self):
        self.assertEqual(parse_args(["--agent-version", "v0", "--frozen", "--split", "dev"]).agent_version, "v0")


if __name__ == "__main__":
    unittest.main()
