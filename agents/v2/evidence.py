"""Evidence grounding: check that LLM 'quotes' really exist in the signal.

An LLM can invent a plausible quote. Each evidence item is classified as:
- ``exact``: the normalised quote is a substring of the normalised signal;
- ``fuzzy``: at least 85 % of its content words (>= 3 words) occur in the signal;
- ``ungrounded``: anything else. Ungrounded quotes are removed from the output
  and counted, which gives a hallucinated-evidence rate per run.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple

WORD = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")
STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "are", "was", "has", "have",
    "its", "into", "not", "but", "you", "your", "our", "their", "can", "will", "all",
}


def signal_text(signal: Dict[str, Any]) -> str:
    """Everything the model was shown: title, description and metadata."""
    # Mirror the prompt layout ("Source: ...", "Title: ..."): models often quote these lines verbatim.
    parts = [
        f"Source: {signal.get('source', '')}",
        f"Title: {signal.get('title', '')}",
        str(signal.get("description", "")),
    ]
    for key, value in (signal.get("metadata") or {}).items():
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        parts.append(f"{key}: {value}")
    return "\n".join(parts)


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(WORD.findall(text))


def _stem(word: str) -> str:
    """Crude prefix stemming so 'removed' matches 'remove' or 'removes'."""
    return word[:5] if len(word) >= 5 else word


def ground_quote(quote: str, source: str) -> str:
    q = _normalise(quote)
    s = _normalise(source)
    if len(q) < 3:
        return "ungrounded"
    if q in s:
        return "exact"
    words = [w for w in q.split() if len(w) >= 3 and w not in STOPWORDS]
    if len(words) >= 3:
        source_stems = {_stem(w) for w in s.split()}
        coverage = sum(_stem(w) in source_stems for w in words) / len(words)
        if coverage >= 0.85:
            return "fuzzy"
    return "ungrounded"


def ground_evidence(quotes: List[str], signal: Dict[str, Any]) -> Tuple[List[str], List[str], Dict[str, int]]:
    """Split quotes into (kept, rejected) and return counts per status."""
    source = signal_text(signal)
    kept: List[str] = []
    rejected: List[str] = []
    counts = {"exact": 0, "fuzzy": 0, "ungrounded": 0}
    for quote in quotes:
        status = ground_quote(str(quote), source)
        counts[status] += 1
        (rejected if status == "ungrounded" else kept).append(str(quote))
    return kept, rejected, counts
