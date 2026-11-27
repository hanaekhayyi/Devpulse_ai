"""Deterministic signal profiling shared by the v2 relevance and risk agents.

The profile is computed once per signal, without any LLM call, and gives the
agents hard facts that a model tends to miss or to hallucinate:

- explicit compatibility markers;
- explicit security markers;
- prompt-injection findings (see ``guards``);
- a GitHub "lure repository" score. Malware/cheat lure campaigns on GitHub
  share recognisable traits: cheat/crack vocabulary, impersonation of paid
  software, topic stuffing, and a repository language (HTML) that contradicts
  the native-code topics it claims (cpp, directx, win32...).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from agents.v2.guards import neutralise

# Explicit compatibility and suspicion markers (deterministic, no LLM).
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


def has_explicit_breaking_marker(text: str) -> bool:
    """Detect a positive compatibility marker without letting an unrelated negation cancel it."""
    for match in BREAKING_PATTERN.finditer(text):
        matched = match.group(0).lower()
        prefix = text[max(0, match.start() - 32):match.start()].lower()
        if matched.startswith("breaking") and re.search(r"\b(?:no|without)\s*$", prefix):
            continue
        return True
    return False


LURE_LEXICON = re.compile(
    r"\b(?:mod[- ]?menu|executor|cheats?|hacks?|aimbot|wallhack|esp|injector|spoofer|unlocker|"
    r"keygen|crack(?:ed)?|activator|license[- ]?key|serial[- ]?key|free[- ]download|full[- ]version|"
    r"sniping|sniper[- ]bot|trainer|fflags?|fastflags?|scripts?[- ]roblox|roblox[- ]scripts?|"
    r"how[- ]to[- ]install|portable[- ]edition|patch(?:ed)?[- ]?(?:fix|pack)?)\b",
    re.IGNORECASE,
)
COMMERCIAL_SOFTWARE = re.compile(
    r"\b(?:matlab|fiddler|photoshop|illustrator|premiere|after[- ]effects|autocad|solidworks|revit|"
    r"sketchup|coreldraw|ableton|fl[- ]studio|vmware|office[- ]?365|microsoft[- ]office|windows[- ]activator|"
    r"adobe|camtasia|davinci[- ]resolve|idm|internet[- ]download[- ]manager|wondershare|filmora)\b",
    re.IGNORECASE,
)
NATIVE_TOPICS = {
    "cpp", "c", "c-plus-plus", "directx", "directx-11", "directx-12", "vulkan", "win32-api",
    "imgui", "cmake", "desktop-app", "windows-app", "windows-10", "windows-11",
}
WEB_ONLY_LANGUAGES = {"html", "css", ""}
SECURITY_PATTERN = re.compile(
    r"\b(?:cve-\d{4}-\d+|ghsa-[a-z0-9-]+|vulnerabilit(?:y|ies)|exploit(?:ed|s)?|remote code execution|rce|"
    r"malware|backdoor|credential stealer|supply[- ]chain attack|security (?:fix|advisory|patch))\b",
    re.IGNORECASE,
)


CORE_FRAMEWORKS = {
    "agno-agi/agno", "langchain-ai/langchain", "openai/openai-python", "huggingface/transformers",
    "pytorch/pytorch", "pydantic/pydantic",
}
VERSION = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")
SUBPACKAGE = re.compile(r"\b([a-z0-9]+(?:-[a-z0-9]+)+)==\d", re.IGNORECASE)


def release_info(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic facts about a GitHub release: version bump type and package scope."""
    if signal.get("source") != "github_releases":
        return {}
    metadata = signal.get("metadata") or {}
    repository = str(metadata.get("repository") or "").lower()
    title = str(signal.get("title", ""))
    tag = str(metadata.get("tag_name") or title)
    info: Dict[str, Any] = {"repository": repository, "core_framework": repository in CORE_FRAMEWORKS}
    match = VERSION.search(tag)
    if match:
        major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)
        info["version"] = match.group(0)
        info["bump"] = "patch" if patch else ("minor" if minor else "major")
    sub = SUBPACKAGE.search(title)
    repo_name = repository.split("/")[-1]
    info["integration_package"] = bool(sub and sub.group(1).lower() != repo_name)
    if info["integration_package"]:
        info["package"] = sub.group(1).lower()
    info["prerelease"] = bool(metadata.get("prerelease"))
    return info


@dataclass
class SignalProfile:
    explicit_breaking_marker: bool
    security_marker: bool
    keyword_suspicion_marker: bool
    lure_score: int
    lure_reasons: List[str] = field(default_factory=list)
    injection_detected: bool = False
    injection_matches: List[str] = field(default_factory=list)
    release: Dict[str, Any] = field(default_factory=dict)
    clean_description: str = ""

    @property
    def is_lure(self) -> bool:
        return self.lure_score >= 2

    @property
    def concrete_suspicion(self) -> bool:
        return self.is_lure or self.keyword_suspicion_marker or self.injection_detected

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("clean_description")
        data["is_lure"] = self.is_lure
        return data


def _lure_analysis(signal: Dict[str, Any]) -> tuple[int, List[str]]:
    if signal.get("source") != "github":
        return 0, []
    metadata = signal.get("metadata") or {}
    topics = [str(t).lower() for t in metadata.get("topics") or []]
    language = str(metadata.get("language") or "").lower()
    haystack = " ".join([str(signal.get("title", "")), str(signal.get("description", "")), " ".join(topics)])
    score = 0
    reasons: List[str] = []

    lexicon_hits = sorted({m.group(0).lower() for m in LURE_LEXICON.finditer(haystack)})
    if lexicon_hits:
        score += min(2, len(lexicon_hits))
        reasons.append(f"cheat/crack vocabulary: {', '.join(lexicon_hits[:4])}")
    commercial = sorted({m.group(0).lower() for m in COMMERCIAL_SOFTWARE.finditer(haystack)})
    if commercial:
        score += 1
        reasons.append(f"names paid software: {', '.join(commercial[:3])}")
    native = NATIVE_TOPICS.intersection(topics)
    if language in WEB_ONLY_LANGUAGES and native:
        score += 1
        reasons.append(f"language '{language or 'none'}' contradicts native topics ({', '.join(sorted(native)[:3])})")
    if len(topics) >= 12:
        score += 1
        reasons.append(f"topic stuffing ({len(topics)} topics)")
    return score, reasons


def profile_signal(signal: Dict[str, Any]) -> SignalProfile:
    title = str(signal.get("title", ""))
    description = str(signal.get("description", ""))
    text = f"{title}\n{description}"
    injection = neutralise(text)
    lure_score, lure_reasons = _lure_analysis(signal)
    clean = neutralise(description).cleaned_text
    return SignalProfile(
        explicit_breaking_marker=has_explicit_breaking_marker(text),
        security_marker=bool(SECURITY_PATTERN.search(text)),
        keyword_suspicion_marker=bool(SUSPICION_PATTERN.search(text)),
        lure_score=lure_score,
        lure_reasons=lure_reasons,
        injection_detected=injection.detected,
        injection_matches=injection.matches,
        release=release_info(signal),
        clean_description=clean,
    )
