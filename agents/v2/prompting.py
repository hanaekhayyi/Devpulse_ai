"""Shared prompt rendering for v2 agents: metadata, computed facts, delimited and sanitised content."""

from __future__ import annotations

from typing import Any, Dict

from agents.v2.guards import escape_delimiters
from agents.v2.profiler import SignalProfile

METADATA_KEYS = (
    "stars", "language", "topics", "downloads", "likes", "pipeline_tag", "points", "comments",
    "published", "published_at", "repository", "tag_name", "prerelease", "author",
)


def render_metadata(signal: Dict[str, Any]) -> str:
    metadata = signal.get("metadata") or {}
    lines = []
    for key in METADATA_KEYS:
        if key in metadata and metadata[key] not in (None, "", []):
            value = metadata[key]
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value[:20])
            lines.append(f"- {key}: {escape_delimiters(str(value))[:200]}")
    return "\n".join(lines) or "- (none)"


def render_release_facts(profile: SignalProfile) -> str:
    """Deterministic release facts, placed outside the untrusted block."""
    info = profile.release
    if not info:
        return ""
    facts = [f"- version bump: {info.get('bump', 'unknown')}"]
    if info.get("integration_package"):
        facts.append(
            f"- scope: sub-package '{info['package']}' of {info['repository']} "
            "(only matters to users of that package)"
        )
    else:
        facts.append(f"- scope: main package of {info['repository']}")
    facts.append(f"- core framework used by the team: {'yes' if info.get('core_framework') else 'no'}")
    if info.get("prerelease"):
        facts.append("- pre-release")
    return "Release facts (computed, trusted):\n" + "\n".join(facts) + "\n"


def render_signal(signal: Dict[str, Any], profile: SignalProfile, max_chars: int) -> str:
    title = escape_delimiters(str(signal.get("title", "Untitled")))
    body = escape_delimiters(profile.clean_description[:max_chars])
    return (
        f"Source: {signal.get('source', 'unknown')}\n"
        f"Metadata:\n{render_metadata(signal)}\n"
        f"{render_release_facts(profile)}"
        f"<untrusted_signal>\nTitle: {title}\n{body}\n</untrusted_signal>"
    )
