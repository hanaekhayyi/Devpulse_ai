"""RiskAgent v1.1 with deterministic post-LLM evidence validation."""

from __future__ import annotations

import re
from typing import Any, Dict

from agents.risk_agent_v1 import RiskAgentV1


BREAKING_PATTERN = re.compile(
    r"\b(?:breaking(?: change)?|backward[- ]incompatible|remove(?:d|s)?\s+[^.\n]{0,80}\b(?:support|python|api|endpoint)|"
    r"drop(?:ped|s)?\s+[^.\n]{0,80}\b(?:support|python|api|endpoint)|eol(?:['’]?d)?\s+python|"
    r"end[- ]of[- ]life|migration required|unsupported\s+python)\b",
    re.IGNORECASE,
)
SUSPICION_PATTERN = re.compile(
    r"\b(?:hack|cheat|malware|crack|executor|keygen|sniping|map[- ]hack|fake antivirus)\b",
    re.IGNORECASE,
)


class RiskAgentV1_1(RiskAgentV1):
    """Keep LLM context analysis, then enforce explicit evidence rules."""

    def assess(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        result = super().assess(signal)
        return self._apply_evidence_rules(signal, result)

    @staticmethod
    def _apply_evidence_rules(signal: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        text = f"{signal.get('title', '')}\n{signal.get('description', '')}"
        explicit_breaking = _has_explicit_breaking_marker(text)
        concrete_suspicion = bool(SUSPICION_PATTERN.search(text))
        corrected = dict(result)
        evidence_strength = "NONE"

        if explicit_breaking:
            corrected["breaking_changes"] = True
            corrected["risk_category"] = "COMPATIBILITY"
            if corrected.get("risk_level") == "LOW":
                corrected["risk_level"] = "MEDIUM"
            evidence = list(corrected.get("evidence") or [])
            evidence.append("Explicit compatibility marker detected in the frozen signal.")
            corrected["evidence"] = list(dict.fromkeys(evidence))
            evidence_strength = "CONFIRMED"
        elif not concrete_suspicion and corrected.get("risk_category") == "SUSPICION":
            corrected["risk_category"] = "NONE"
            corrected["risk_level"] = "LOW"
            corrected["concerns"] = []
            corrected["evidence"] = ["No concrete suspicion marker found in the frozen signal."]
        elif concrete_suspicion and corrected.get("risk_category") == "SUSPICION":
            evidence_strength = "INDICATOR"

        if corrected.get("risk_category") == "SECURITY":
            security_text = re.search(r"\b(?:cve|vulnerability|exploit|rce|malware|breach)\b", text, re.IGNORECASE)
            evidence_strength = "CONFIRMED" if security_text else "INDICATOR"

        corrected["post_validation"] = {
            "explicit_breaking_marker": explicit_breaking,
            "concrete_suspicion_marker": concrete_suspicion,
            "evidence_strength": evidence_strength,
        }
        corrected["evidence_strength"] = evidence_strength
        return corrected


def _has_explicit_breaking_marker(text: str) -> bool:
    """Detect a positive marker without letting an unrelated negation cancel it."""
    for match in BREAKING_PATTERN.finditer(text):
        matched = match.group(0).lower()
        prefix = text[max(0, match.start() - 32):match.start()].lower()
        if matched.startswith("breaking") and re.search(r"\b(?:no|without)\s*$", prefix):
            continue
        return True
    return False
