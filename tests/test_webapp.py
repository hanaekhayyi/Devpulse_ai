"""Offline tests for the local web app API (no LLM call)."""

import unittest

from starlette.testclient import TestClient

from webapp.server import app


class WebAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_index_is_served_without_cache(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SignalGuard", response.text)
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_overview(self):
        data = self.client.get("/api/overview").json()
        self.assertEqual(data["dataset"]["signals"], 72)
        self.assertIn("relevance", data["models"])
        self.assertGreater(data["tests"], 0)
        self.assertEqual(len(data["evaluation"]["items"]), 6)

    def test_benchmarks_have_all_versions_on_test(self):
        data = self.client.get("/api/benchmarks").json()
        versions = {s["version"] for s in data["gold"]["v4"]["test"]}
        self.assertTrue({"v0", "v1.1", "v2"} <= versions)

    def test_signals_include_gold_and_predictions(self):
        rows = self.client.get("/api/signals").json()["signals"]
        self.assertEqual(len(rows), 72)
        self.assertTrue(all("gold" in r for r in rows))
        self.assertTrue(any(r["prediction"] for r in rows))

    def test_feed_is_ranked_by_relevance_and_keeps_risky_signals(self):
        data = self.client.get("/api/feed").json()
        scores = [i["relevance"]["score"] or 0 for i in data["items"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreater(data["counts"]["elevated_risk"], 0)
        self.assertTrue(any(i["elevated_risk"] for i in data["items"]))
        self.assertEqual(len({i["signal_id"] for i in data["items"]}), len(data["items"]))

    def test_unknown_run_returns_404(self):
        self.assertEqual(self.client.get("/api/runs/doesnotexist").status_code, 404)


if __name__ == "__main__":
    unittest.main()
