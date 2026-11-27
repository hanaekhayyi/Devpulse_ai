"""Evidence-based risk agent (SignalGuard v1)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL


DEFAULT_MODEL = os.environ.get(
    "MODEL_RISK_V1",
    os.environ.get("MODEL_RISK", "mistralai/mistral-small-3.2-24b-instruct"),
)
RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
RISK_CATEGORIES = {"NONE", "SECURITY", "COMPATIBILITY", "DEPRECATION", "MIGRATION", "SUSPICION"}


class RiskAgentV1:
    """Assess risk while distinguishing evidence, compatibility and suspicion."""

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or DEFAULT_MODEL
        self.agent = Agent(
            name="Evidence Risk Assessor v1",
            model=OpenAIChat(
                id=self.model_id,
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL,
            ),
            role="Assesses technical risk from explicit signal evidence",
            instructions=[
                "Use only evidence present in the signal.",
                "Do not infer a breaking change from a major version number alone.",
                "A suspicion without proof is SUSPICION and normally MEDIUM, not HIGH.",
                "Return JSON only and include concrete evidence snippets.",
            ],
            markdown=True,
        )

    def assess(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""Assess this signal for developer and security risk.

Rules:
- risk_level must be LOW, MEDIUM, HIGH, or CRITICAL.
- risk_category must be NONE, SECURITY, COMPATIBILITY, DEPRECATION, MIGRATION, or SUSPICION.
- Set breaking_changes=true only for explicit backward-incompatible changes, removals,
  required migrations, or ended support. A major version number alone is insufficient.
- HIGH/CRITICAL require direct evidence such as a vulnerability, exploit, breach, or severe
  operational impact. Suspicious naming or behavior without proof is SUSPICION and MEDIUM.

Signal source: {signal.get('source', 'unknown')}
Signal title: {signal.get('title', 'Untitled')}
Signal content:
<signal_content>
{signal.get('description', '')[:1600]}
</signal_content>

Return ONLY this JSON object:
{{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "risk_category": "NONE|SECURITY|COMPATIBILITY|DEPRECATION|MIGRATION|SUSPICION",
  "concerns": ["short concern"],
  "evidence": ["short quote or factual observation"],
  "breaking_changes": true
}}"""
        try:
            response = self.agent.run(prompt, stream=False)
            return self._parse_response(response.content, signal)
        except Exception as exc:
            return self._fallback_assess(signal, str(exc))

    def assess_batch(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{**signal, "risk": self.assess(signal)} for signal in signals]

    def _parse_response(self, content: str, signal: Dict[str, Any]) -> Dict[str, Any]:
        try:
            text = content.strip()
            if "```" in text:
                text = text.split("```", 2)[1].replace("json", "", 1).strip()
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError("Expected a JSON object")
            level = str(result.get("risk_level", "")).upper()
            category = str(result.get("risk_category", "")).upper()
            if level not in RISK_LEVELS or category not in RISK_CATEGORIES:
                raise ValueError("Invalid risk level or category")
            if not isinstance(result.get("breaking_changes"), bool):
                raise ValueError("breaking_changes must be boolean")
            concerns = result.get("concerns", [])
            evidence = result.get("evidence", [])
            if not isinstance(concerns, list) or not isinstance(evidence, list):
                raise ValueError("concerns and evidence must be lists")
            return {
                **result,
                "risk_level": level,
                "risk_category": category,
                "concerns": [str(item) for item in concerns],
                "evidence": [str(item) for item in evidence],
                "used_fallback": False,
                "fallback_reason": None,
            }
        except (json.JSONDecodeError, IndexError, TypeError, ValueError) as exc:
            return self._fallback_assess(signal, f"Invalid risk response: {exc}")

    def _fallback_assess(self, signal: Dict[str, Any], error: str) -> Dict[str, Any]:
        text = f"{signal.get('title', '')} {signal.get('description', '')}".lower()
        breaking = bool(re.search(r"breaking|backward[- ]incompatible|remove(?:d|s)? .*support|eol|end[- ]of[- ]life|migration required", text))
        explicit_security = bool(re.search(r"cve|vulnerability|exploit|rce|remote code execution|breach|malware", text))
        suspicion = bool(re.search(r"hack|cheat|executor|keygen|crack|sniping|map[- ]hack|fake antivirus", text))
        if explicit_security:
            level, category = "HIGH", "SECURITY"
        elif suspicion:
            level, category = "MEDIUM", "SUSPICION"
        elif breaking:
            level, category = "MEDIUM", "COMPATIBILITY"
        else:
            level, category = "LOW", "NONE"
        return {
            "risk_level": level,
            "risk_category": category,
            "concerns": ["Explicit risk or compatibility wording detected."] if level != "LOW" else [],
            "evidence": [signal.get("title", "")],
            "breaking_changes": breaking,
            "used_fallback": True,
            "fallback_reason": error,
        }
