"""Rubric-based relevance agent (SignalGuard v1)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL


DEFAULT_MODEL = os.environ.get(
    "MODEL_RELEVANCE_V1",
    os.environ.get("MODEL_RELEVANCE", "mistralai/mistral-small-3.2-24b-instruct"),
)


class RelevanceAgentV1:
    """Score relevance with explicit, weighted criteria.

    Weights: novelty 25, technical relevance 30, applicability 25,
    timeliness 20. The total is therefore always in the 0-100 range.
    """

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or DEFAULT_MODEL
        self.agent = Agent(
            name="Rubric Relevance Scorer v1",
            model=OpenAIChat(
                id=self.model_id,
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL,
            ),
            role="Scores technical signals with an explicit relevance rubric",
            instructions=[
                "Use the four rubric criteria and their exact maximum weights.",
                "Do not infer importance from popularity alone.",
                "Use only evidence present in the signal.",
                "Return JSON only and keep reasoning concise.",
            ],
            markdown=True,
        )

    def score(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""Score this signal for AI/ML developer relevance.

Rubric:
- novelty: 0-25 (new idea, release, result, or capability)
- technical_relevance: 0-30 (direct relevance to AI/ML engineering)
- applicability: 0-25 (practical usefulness or actionability)
- timeliness: 0-20 (why developers should care now)

The total score must equal the sum of the four criteria.
Use only the evidence in the signal. Popularity alone is not enough.

Signal source: {signal.get('source', 'unknown')}
Signal title: {signal.get('title', 'Untitled')}
Signal description:
<signal_content>
{signal.get('description', '')[:1200]}
</signal_content>

Return ONLY this JSON object:
{{
  "novelty": <0-25>,
  "technical_relevance": <0-30>,
  "applicability": <0-25>,
  "timeliness": <0-20>,
  "score": <sum 0-100>,
  "reasoning": "<one concise sentence>"
}}"""

        try:
            response = self.agent.run(prompt, stream=False)
            return self._parse_response(response.content, signal)
        except Exception as exc:
            return self._fallback_score(signal, str(exc))

    def score_batch(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{**signal, "relevance": self.score(signal)} for signal in signals]

    def _parse_response(self, content: str, signal: Dict[str, Any]) -> Dict[str, Any]:
        try:
            text = content.strip()
            if "```" in text:
                text = text.split("```", 2)[1].replace("json", "", 1).strip()
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError("Expected a JSON object")

            limits = {
                "novelty": 25,
                "technical_relevance": 30,
                "applicability": 25,
                "timeliness": 20,
            }
            values = {key: result.get(key) for key in limits}
            if not all(isinstance(value, (int, float)) for value in values.values()):
                raise ValueError("Missing rubric score")
            if any(value < 0 or value > limit for (key, limit), value in zip(limits.items(), values.values())):
                raise ValueError("Rubric score outside its allowed range")
            score = sum(values.values())
            if result.get("score") != score:
                raise ValueError("Total score does not match rubric sum")
            if not 0 <= score <= 100:
                raise ValueError("Total score outside 0-100")

            return {
                **result,
                "score": int(score),
                "used_fallback": False,
                "fallback_reason": None,
            }
        except (json.JSONDecodeError, IndexError, TypeError, ValueError) as exc:
            return self._fallback_score(signal, f"Invalid rubric response: {exc}")

    def _fallback_score(self, signal: Dict[str, Any], error: str) -> Dict[str, Any]:
        metadata = signal.get("metadata", {})
        novelty = 10
        technical = 15
        applicability = 10
        timeliness = 10
        if signal.get("source") in {"github_releases", "huggingface", "arxiv"}:
            technical += 5
        if metadata.get("stars", 0) > 100 or metadata.get("downloads", 0) > 10000:
            applicability += 5
        if metadata.get("published") or metadata.get("published_at"):
            timeliness += 5
        score = novelty + technical + applicability + timeliness
        return {
            "novelty": novelty,
            "technical_relevance": technical,
            "applicability": applicability,
            "timeliness": timeliness,
            "score": min(score, 100),
            "reasoning": "Rubric fallback used because the model response was unavailable or invalid.",
            "used_fallback": True,
            "fallback_reason": error,
        }
