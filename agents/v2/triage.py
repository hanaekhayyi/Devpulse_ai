"""Risk triage: decide which signals need the LLM risk analysis (SignalGuard v2).

Risk on this dataset comes from three kinds of artifacts: repositories
(lures, malware), library releases (breaking changes) and model repositories
(remote code). Papers, blog posts and HN discussions only carry risk when an
explicit marker is present. The fast path keeps the deterministic arbitration
(markers, lures, injection) and only skips the model call.

Offline validation on the saved v2 runs (gold v4.1): 50 % of risk LLM calls
skipped on DEV and on TEST, 0 risky signal skipped, 0 prediction changed.
"""

from __future__ import annotations

from typing import Any, Dict

from agents.v2.profiler import SignalProfile, profile_signal
from agents.v2.risk import arbitrate

ARTIFACT_SOURCES = {"github", "github_releases", "huggingface"}


def needs_llm_risk(signal: Dict[str, Any], profile: SignalProfile | None = None) -> bool:
    profile = profile or profile_signal(signal)
    return (
        signal.get("source") in ARTIFACT_SOURCES
        or profile.explicit_breaking_marker
        or profile.security_marker
        or profile.keyword_suspicion_marker
        or profile.injection_detected
        or profile.is_lure
    )


def fast_path_risk(signal: Dict[str, Any], profile: SignalProfile | None = None) -> Dict[str, Any]:
    """Deterministic assessment with the same output shape as RiskAgentV2.assess."""
    profile = profile or profile_signal(signal)
    raw = {"risk_level": "LOW", "risk_category": "NONE", "breaking_changes": False,
           "concerns": [], "evidence_quotes": []}
    result = arbitrate(signal, profile, raw)
    result.update(used_fallback=False, fallback_reason=None, triaged=True,
                  usage={"attempts": 0, "cache_hit": False, "latency_ms": 0.0, "input_tokens": 0,
                         "output_tokens": 0, "cost_usd": 0.0, "errors": []})
    return result
