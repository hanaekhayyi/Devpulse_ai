import unittest

import httpx

from adapters.github_releases import fetch_github_releases


class GithubReleasesAdapterTests(unittest.TestCase):
    def test_normalizes_release_to_signal_schema(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 123,
                        "tag_name": "v2.0.0",
                        "name": "v2.0.0",
                        "body": "BREAKING: remove the legacy endpoint.",
                        "html_url": "https://github.com/acme/sdk/releases/tag/v2.0.0",
                        "published_at": "2026-11-24T10:00:00Z",
                        "created_at": "2026-11-24T09:00:00Z",
                        "draft": False,
                        "prerelease": False,
                    }
                ],
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            signals = fetch_github_releases(
                limit=1,
                repositories=["acme/sdk"],
                client=client,
            )
        finally:
            client.close()

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["source"], "github_releases")
        self.assertEqual(signals[0]["id"], "acme/sdk:123")
        self.assertIn("BREAKING", signals[0]["description"])
        self.assertEqual(signals[0]["metadata"]["tag_name"], "v2.0.0")

    def test_ignores_drafts(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "tag_name": "draft", "draft": True},
                    {"id": 2, "tag_name": "v1.0.0", "draft": False},
                ],
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            signals = fetch_github_releases(
                limit=2,
                repositories=["acme/sdk"],
                client=client,
            )
        finally:
            client.close()

        self.assertEqual([signal["id"] for signal in signals], ["acme/sdk:2"])


if __name__ == "__main__":
    unittest.main()
