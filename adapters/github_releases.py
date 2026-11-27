"""GitHub Releases adapter for real-world breaking-change signals.

The adapter reads published releases from a curated list of repositories. It
keeps the release notes in the normal signal schema so RiskAgent can inspect
real migration, deprecation, and API-compatibility announcements.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, Iterable, List

import httpx


DEFAULT_REPOSITORIES = (
    "openai/openai-python",
    "langchain-ai/langchain",
    "agno-agi/agno",
    "pydantic/pydantic",
    "huggingface/transformers",
    "pytorch/pytorch",
)


def _configured_repositories(
    repositories: Iterable[str] | None,
) -> List[str]:
    if repositories is not None:
        return [repo.strip() for repo in repositories if repo.strip()]

    configured = os.getenv("GITHUB_RELEASE_REPOSITORIES", "")
    if configured.strip():
        return [repo.strip() for repo in configured.split(",") if repo.strip()]

    return list(DEFAULT_REPOSITORIES)


def fetch_github_releases(
    limit: int = 12,
    repositories: Iterable[str] | None = None,
    client: httpx.Client | None = None,
) -> List[Dict[str, Any]]:
    """Fetch recent published releases from curated GitHub repositories.

    Args:
        limit: Maximum total number of releases to return.
        repositories: Optional ``owner/repository`` overrides.
        client: Optional HTTP client, primarily useful for tests.

    Returns:
        Signals using the common DevPulseAI schema.
    """
    if limit <= 0:
        return []

    repos = _configured_repositories(repositories)
    if not repos:
        return []

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "DevPulseAI-SignalGuard",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    per_repo = min(max(2, math.ceil(limit / len(repos)) + 2), 20)
    http_client = client or httpx.Client(timeout=15.0, headers=headers)
    owns_client = client is None
    signals: List[Dict[str, Any]] = []

    try:
        for repository in repos:
            endpoint = (
                f"https://api.github.com/repos/{repository}/releases"
                f"?per_page={per_repo}&page=1"
            )
            try:
                response = http_client.get(endpoint, headers=headers)
                response.raise_for_status()
                releases = response.json()
            except httpx.HTTPError as exc:
                print(f"[GitHub Releases Adapter] HTTP error for {repository}: {exc}")
                continue
            except ValueError as exc:
                print(f"[GitHub Releases Adapter] Invalid JSON for {repository}: {exc}")
                continue

            if not isinstance(releases, list):
                continue

            for release in releases:
                if release.get("draft", False):
                    continue

                release_id = release.get("id") or release.get("tag_name")
                if not release_id:
                    continue

                tag_name = release.get("tag_name") or "unversioned"
                release_name = release.get("name") or tag_name
                body = (release.get("body") or "").strip()
                description = body[:2000] if body else "No release notes provided."

                signals.append(
                    {
                        "id": f"{repository}:{release_id}",
                        "source": "github_releases",
                        "title": f"{repository} {release_name}",
                        "description": description,
                        "url": release.get(
                            "html_url",
                            f"https://github.com/{repository}/releases",
                        ),
                        "metadata": {
                            "repository": repository,
                            "tag_name": tag_name,
                            "published_at": release.get("published_at", ""),
                            "created_at": release.get("created_at", ""),
                            "prerelease": bool(release.get("prerelease", False)),
                        },
                    }
                )

    finally:
        if owns_client:
            http_client.close()

    signals.sort(
        key=lambda signal: signal["metadata"].get("published_at", ""),
        reverse=True,
    )
    return signals[:limit]


if __name__ == "__main__":
    for release in fetch_github_releases(limit=5):
        print(f"- {release['title']}")
