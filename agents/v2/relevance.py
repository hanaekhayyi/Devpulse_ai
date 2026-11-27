"""RelevanceAgentV2: anchored rubric + structured output + deterministic caps."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import config  # noqa: F401  (loads .env and provider model defaults)
from agents.v2.guards import DATA_HANDLING_INSTRUCTIONS
from agents.v2.profiler import profile_signal
from agents.v2.prompting import render_signal
from agents.v2.runner import ResponseCache, StructuredLLM
from agents.v2.schemas import RelevanceRubric

PROMPT_VERSION = "relevance-v2.2"
LURE_RELEVANCE_CAP = 10

# Upper bounds stated in the rubric for release types that can be identified
# deterministically. The model tends to ignore them (it scored every release
# ~22/25 applicability on DEV), so they are enforced after the call.
RELEASE_CAPS = {
    "sub_package": {"novelty": 8, "technical_relevance": 18, "applicability": 12, "timeliness": 10},
    "patch": {"novelty": 8, "applicability": 16, "timeliness": 12},
}


def release_caps(profile) -> tuple[str, dict]:
    info = profile.release
    if not info:
        return "", {}
    if info.get("integration_package"):
        return "sub_package", RELEASE_CAPS["sub_package"]
    if info.get("bump") == "patch":
        return "patch", RELEASE_CAPS["patch"]
    return "", {}

DEFAULT_MODEL = os.environ.get(
    "MODEL_RELEVANCE_V2",
    os.environ.get("MODEL_RELEVANCE", "mistralai/mistral-small-3.2-24b-instruct"),
)

INSTRUCTIONS = [
    "You score technical signals for an engineering team that builds LLM applications and "
    "multi-agent systems in Python (Agno, LangChain, OpenAI SDK, Hugging Face, PyTorch).",
    "Score each rubric criterion independently with the anchors given in the prompt.",
    "Use only the evidence in the signal and its metadata. Popularity alone is not relevance.",
    *DATA_HANDLING_INSTRUCTIONS,
]

RUBRIC = """Rubric (score each criterion with these anchors):
novelty 0-25:
  0-5 old, well known or a rehash | 6-12 incremental | 13-19 notable new release or result | 20-25 major new capability
technical_relevance 0-30:
  0-5 off-topic or non-technical (career advice, business, marketing, listicles, games)
  6-14 adjacent (ML research in a narrow non-LLM domain, generic software news)
  15-24 relevant to applied ML / model usage | 25-30 core to building LLM or agent applications
applicability 0-25:
  0-5 nothing actionable | 6-12 ideas only, no usable artifact
  13-19 usable with effort (paper with code, model to evaluate) | 20-25 directly usable now (library release, open model, tool)
timeliness 0-20:
  0-5 no time pressure or old news | 6-12 moderately recent | 13-20 calls for action now (new release, upgrade, security fix)
Guidance:
- Clickbait, listicles, career or business posts score low on technical_relevance.
- A research preprint is "ideas only" (applicability 6-12) unless it releases code, weights or a tool,
  and it rarely calls for action now (timeliness 3-8).
- Papers in narrow application domains (physics, medicine, radiology, telecom...) score at most 10 on technical_relevance.
- Repositories that look like game cheats, cracks, pirated software or spam lures score near 0 everywhere.
- New open-weight foundation models are highly applicable.
Library releases (use the computed release facts; score what the visible notes actually change):
- sub-package release (e.g. a single provider/vector-store connector): technical_relevance 10-18,
  applicability 6-12, novelty 3-8, timeliness 4-10; a dropped Python version is a compatibility note, not a capability.
- patch / maintenance release (fixes, dependency bumps, small behaviour changes): novelty 3-8,
  applicability 10-16, timeliness 6-12.
- minor release adding one or two API features: novelty 8-12, applicability 12-18.
- release adding major capabilities or new model architectures to a core library: novelty 13-19, applicability 15-20.
- Release notes are often truncated: judge only the visible content, never assume more."""


class RelevanceAgentV2:
    version = "v2"

    def __init__(self, model_id: Optional[str] = None, cache: Optional[ResponseCache] = None, **llm_kwargs: Any):
        self.model_id = model_id or DEFAULT_MODEL
        self.llm = StructuredLLM(
            name="Rubric Relevance Scorer v2",
            instructions=INSTRUCTIONS,
            schema=RelevanceRubric,
            model_id=self.model_id,
            prompt_version=PROMPT_VERSION,
            cache=cache,
            **llm_kwargs,
        )

    def build_prompt(self, signal: Dict[str, Any], profile) -> str:
        return f"{RUBRIC}\n\nSignal:\n{render_signal(signal, profile, max_chars=1500)}"

    def score(self, signal: Dict[str, Any], *, cache_salt: str = "") -> Dict[str, Any]:
        profile = profile_signal(signal)
        call = self.llm.run(self.build_prompt(signal, profile), cache_salt=cache_salt)
        if call.ok:
            rubric: RelevanceRubric = call.output  # type: ignore[assignment]
            result = {**rubric.model_dump(), "score": rubric.score, "used_fallback": False, "fallback_reason": None}
        else:
            result = _fallback_score(signal, "; ".join(call.stats.errors) or "unknown error")

        adjustments: List[str] = []
        kind, caps = release_caps(profile)
        if caps and not result["used_fallback"]:
            for criterion, cap in caps.items():
                if result[criterion] > cap:
                    adjustments.append(f"{kind} release: {criterion} {result[criterion]} -> {cap}")
                    result[criterion] = cap
            result["score"] = sum(result[c] for c in ("novelty", "technical_relevance", "applicability", "timeliness"))
        if profile.is_lure and result["score"] > LURE_RELEVANCE_CAP:
            adjustments.append(f"capped from {result['score']} to {LURE_RELEVANCE_CAP}: lure repository")
            result["score"] = LURE_RELEVANCE_CAP
        result["adjustments"] = adjustments
        result["profile"] = profile.to_dict()
        result["usage"] = call.stats.to_dict()
        return result

    def score_batch(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{**signal, "relevance": self.score(signal)} for signal in signals]


def _fallback_score(signal: Dict[str, Any], error: str) -> Dict[str, Any]:
    metadata = signal.get("metadata") or {}
    parts = {"novelty": 10, "technical_relevance": 15, "applicability": 10, "timeliness": 10}
    if signal.get("source") in {"github_releases", "huggingface", "arxiv"}:
        parts["technical_relevance"] += 5
    if (metadata.get("stars") or 0) > 100 or (metadata.get("downloads") or 0) > 10000:
        parts["applicability"] += 5
    return {
        **parts,
        "score": sum(parts.values()),
        "reasoning": "Heuristic fallback: model unavailable or returned an invalid response.",
        "used_fallback": True,
        "fallback_reason": error,
    }
