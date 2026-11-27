"""SynthesisAgentV2: hybrid digest — facts computed in Python, prose written by the LLM.

The original SynthesisAgent built an Agno agent but never called it. Here:

1. Python computes every fact (counts, priority ranking, risk breakdown).
2. The LLM writes the executive summary, the "why it matters" notes and the
   recommendations, using a Pydantic ``output_schema``.
3. Python verifies the answer:
   - every cited ``signal_id`` must belong to the ranked input (unknown ids are
     removed and counted);
   - every number in the summary must be a computed fact or appear in a cited
     title (otherwise the summary is replaced by the deterministic one);
   - if nothing verifiable is left, the whole digest falls back to Python.
4. The fallback is explicit (``synthesis.used_fallback`` + reason).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

import config  # noqa: F401  (loads .env and provider defaults)
from config import HIGH_RELEVANCE_THRESHOLD
from agents.v2.guards import DATA_HANDLING_INSTRUCTIONS, escape_delimiters, neutralise
from agents.v2.runner import ResponseCache, StructuredLLM

PROMPT_VERSION = "synthesis-v2.0"
RISK_MULTIPLIER = {"CRITICAL": 2.0, "HIGH": 1.5, "MEDIUM": 1.0, "LOW": 0.8}
TOP_N_FOR_LLM = 8
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w.])")

DEFAULT_MODEL = os.environ.get(
    "MODEL_SYNTHESIS_V2",
    os.environ.get("MODEL_SYNTHESIS", "mistralai/mistral-small-3.2-24b-instruct"),
)


class KeySignal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal_id: str = Field(description="Exact signal_id copied from the list")
    why_it_matters: str = Field(description="One sentence for the engineering team")


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(description="Concrete action for the team")
    signal_ids: List[str] = Field(description="signal_id values that justify the action")


class DigestLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executive_summary: str = Field(description="2-4 sentences; only numbers from the provided facts")
    key_signals: List[KeySignal]
    recommendations: List[Recommendation]


INSTRUCTIONS = [
    "You write the weekly technology digest for an engineering team building LLM and multi-agent applications.",
    "The facts block is computed by code and is authoritative: never change, recompute or invent numbers.",
    "Cite signals only by their exact signal_id from the provided list.",
    "Every recommendation must be actionable and justified by at least one signal_id.",
    *DATA_HANDLING_INSTRUCTIONS,
]


def priority_score(signal: Dict[str, Any]) -> float:
    relevance = signal.get("relevance", {}).get("score", 50) or 0
    return relevance * RISK_MULTIPLIER.get(signal.get("risk", {}).get("risk_level", "LOW"), 1.0)


def signal_key(signal: Dict[str, Any]) -> str:
    return f"{signal.get('source', '')}:{signal.get('id', '')}"


def compute_facts(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_level = {level: 0 for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")}
    by_category: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    for s in signals:
        risk = s.get("risk", {})
        by_level[risk.get("risk_level", "LOW")] = by_level.get(risk.get("risk_level", "LOW"), 0) + 1
        category = risk.get("risk_category", "NONE")
        by_category[category] = by_category.get(category, 0) + 1
        by_source[s.get("source", "unknown")] = by_source.get(s.get("source", "unknown"), 0) + 1
    return {
        "total_signals": len(signals),
        "high_relevance_signals": sum(
            1 for s in signals if s.get("relevance", {}).get("score", 0) >= HIGH_RELEVANCE_THRESHOLD
        ),
        "high_relevance_threshold": HIGH_RELEVANCE_THRESHOLD,
        "risk_levels": by_level,
        "risk_categories": by_category,
        "breaking_changes": sum(1 for s in signals if s.get("risk", {}).get("breaking_changes")),
        "signals_by_source": by_source,
    }


def _allowed_numbers(facts: Dict[str, Any], cited: List[Dict[str, Any]]) -> set[str]:
    allowed: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            allowed.add(str(value))
    walk(facts)
    for s in cited:
        allowed.update(NUMBER.findall(str(s.get("title", ""))))
        allowed.add(str(s.get("relevance", {}).get("score", "")))
    return allowed


def deterministic_summary(facts: Dict[str, Any], ranked: List[Dict[str, Any]]) -> str:
    if not ranked:
        return "No signals to summarize."
    levels = facts["risk_levels"]
    parts = [f"Analyzed {facts['total_signals']} signals; {facts['high_relevance_signals']} are high-relevance "
             f"(score >= {facts['high_relevance_threshold']})."]
    if levels["CRITICAL"]:
        parts.append(f"{levels['CRITICAL']} critical-risk signal(s).")
    if levels["HIGH"]:
        parts.append(f"{levels['HIGH']} high-risk signal(s).")
    if levels["MEDIUM"]:
        parts.append(f"{levels['MEDIUM']} medium-risk signal(s) to review.")
    if facts["breaking_changes"]:
        parts.append(f"{facts['breaking_changes']} release(s) with breaking changes.")
    parts.append(f"Top signal: {ranked[0].get('title', 'Unknown')}.")
    return " ".join(parts)


def deterministic_recommendations(ranked: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fixes the v0 wording bug: HIGH and CRITICAL are reported separately."""
    def ids(level: str) -> List[str]:
        return [signal_key(s) for s in ranked if s.get("risk", {}).get("risk_level") == level]

    recs: List[Dict[str, Any]] = []
    if ids("CRITICAL"):
        recs.append({"action": f"Review {len(ids('CRITICAL'))} critical-risk signal(s) immediately",
                     "signal_ids": ids("CRITICAL")})
    if ids("HIGH"):
        recs.append({"action": f"Review {len(ids('HIGH'))} high-risk signal(s)", "signal_ids": ids("HIGH")})
    breaking = [signal_key(s) for s in ranked if s.get("risk", {}).get("breaking_changes")]
    if breaking:
        recs.append({"action": "Check compatibility before upgrading these releases", "signal_ids": breaking})
    suspicious = [signal_key(s) for s in ranked if s.get("risk", {}).get("risk_category") == "SUSPICION"]
    if suspicious:
        recs.append({"action": "Do not install or star these suspicious repositories", "signal_ids": suspicious})
    top = [signal_key(s) for s in ranked
           if s.get("relevance", {}).get("score", 0) >= HIGH_RELEVANCE_THRESHOLD][:5]
    if top:
        recs.append({"action": f"Prioritize {len(top)} high-relevance item(s)", "signal_ids": top})
    return recs or [{"action": "No urgent actions required", "signal_ids": []}]


class SynthesisAgentV2:
    version = "v2"

    def __init__(self, model_id: Optional[str] = None, cache: Optional[ResponseCache] = None,
                 use_llm: bool = True, **llm_kwargs: Any):
        self.model_id = model_id or DEFAULT_MODEL
        self.use_llm = use_llm
        self.llm = StructuredLLM(
            name="Digest Writer v2", instructions=INSTRUCTIONS, schema=DigestLLM,
            model_id=self.model_id, prompt_version=PROMPT_VERSION, cache=cache, **llm_kwargs,
        )

    def build_prompt(self, facts: Dict[str, Any], top: List[Dict[str, Any]]) -> str:
        lines = []
        for s in top:
            risk = s.get("risk", {})
            description = escape_delimiters(neutralise(str(s.get("description", ""))).cleaned_text[:240])
            lines.append(
                f"- signal_id: {signal_key(s)} | source: {s.get('source')} | relevance: "
                f"{s.get('relevance', {}).get('score')} | risk: {risk.get('risk_level')}/{risk.get('risk_category')}"
                f" | breaking: {bool(risk.get('breaking_changes'))}\n  title: {escape_delimiters(str(s.get('title', '')))}"
                f"\n  description: {description}"
            )
        return (
            f"Facts (computed, authoritative):\n{json.dumps(facts, indent=1)}\n\n"
            f"Highest-priority signals:\n<untrusted_signal>\n" + "\n".join(lines) + "\n</untrusted_signal>\n\n"
            "Write: executive_summary (2-4 sentences), key_signals (3-5 items), recommendations (2-5 items)."
        )

    def synthesize(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        ranked = sorted(signals, key=priority_score, reverse=True)
        facts = compute_facts(signals)
        by_id = {signal_key(s): s for s in ranked[:TOP_N_FOR_LLM]}
        digest: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_signals": len(signals),
            "facts": facts,
            "priority_signals": ranked[:5],
            "signals_by_source": _group(ranked),
        }
        synthesis = {"mode": "deterministic", "used_fallback": False, "fallback_reason": None,
                     "rejected_signal_ids": [], "summary_replaced": False, "usage": None}

        llm_out: Optional[DigestLLM] = None
        if self.use_llm and ranked:
            call = self.llm.run(self.build_prompt(facts, list(by_id.values())))
            synthesis["usage"] = call.stats.to_dict()
            if call.ok:
                llm_out = call.output  # type: ignore[assignment]
            else:
                synthesis.update(used_fallback=True,
                                 fallback_reason="; ".join(call.stats.errors) or "invalid response")

        if llm_out is not None:
            verified = verify_digest(llm_out, by_id, facts)
            synthesis.update(rejected_signal_ids=verified["rejected_ids"],
                             summary_replaced=verified["summary_replaced"])
            if verified["key_signals"] or verified["recommendations"]:
                synthesis["mode"] = "llm"
                digest["executive_summary"] = verified["summary"] or deterministic_summary(facts, ranked)
                digest["key_signals"] = verified["key_signals"]
                digest["recommendations"] = verified["recommendations"] or deterministic_recommendations(ranked)
            else:
                synthesis.update(used_fallback=True, fallback_reason="no verifiable content in LLM digest")

        if synthesis["mode"] == "deterministic":
            digest["executive_summary"] = deterministic_summary(facts, ranked)
            digest["key_signals"] = [
                {"signal_id": signal_key(s), "title": s.get("title"),
                 "why_it_matters": s.get("relevance", {}).get("reasoning", "")}
                for s in ranked[:3]
            ]
            digest["recommendations"] = deterministic_recommendations(ranked)
        digest["synthesis"] = synthesis
        return digest


def verify_digest(out: DigestLLM, by_id: Dict[str, Dict[str, Any]], facts: Dict[str, Any]) -> Dict[str, Any]:
    rejected: List[str] = []
    key_signals = []
    for item in out.key_signals:
        if item.signal_id in by_id:
            key_signals.append({"signal_id": item.signal_id, "title": by_id[item.signal_id].get("title"),
                                "why_it_matters": item.why_it_matters})
        else:
            rejected.append(item.signal_id)
    recommendations = []
    for rec in out.recommendations:
        valid = [i for i in rec.signal_ids if i in by_id]
        rejected.extend(i for i in rec.signal_ids if i not in by_id)
        if valid:
            recommendations.append({"action": rec.action, "signal_ids": valid})
    cited = [by_id[k["signal_id"]] for k in key_signals]
    allowed = _allowed_numbers(facts, cited or list(by_id.values()))
    unknown_numbers = [n for n in NUMBER.findall(out.executive_summary) if n not in allowed]
    return {
        "summary": None if unknown_numbers else out.executive_summary,
        "summary_replaced": bool(unknown_numbers),
        "unknown_numbers": unknown_numbers,
        "key_signals": key_signals,
        "recommendations": recommendations,
        "rejected_ids": list(dict.fromkeys(rejected)),
    }


def _group(signals: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for s in signals:
        grouped.setdefault(s.get("source", "unknown"), []).append(s)
    return grouped
