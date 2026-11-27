"""Freeze a stable signal dataset for SignalGuard evaluation.

This script calls the existing adapters, normalizes and deduplicates the
results with SignalCollector, validates the common signal schema, and writes:

    data/signals_frozen.json
    data/dev_gold.json
    data/test_gold.json

The *_gold files are annotation templates. They intentionally contain empty
labels that must be reviewed before evaluation.

Usage:
    python scripts/freeze_signals.py
    python scripts/freeze_signals.py --include-releases --output-dir data/benchmark
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


# Make project-root imports work when the script is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.arxiv import fetch_arxiv_papers
from adapters.github import fetch_github_trending
from adapters.hackernews import fetch_hackernews_stories
from adapters.huggingface import fetch_huggingface_models
from adapters.medium import fetch_medium_blogs
from agents.signal_collector import SignalCollector


BASE_SOURCES = ("github", "arxiv", "hackernews", "medium", "huggingface")
REQUIRED_FIELDS = ("id", "source", "title", "description", "url", "metadata")


def collect_raw_signals(
    per_source: int, include_releases: bool = False
) -> List[Dict[str, Any]]:
    """Fetch at most ``per_source`` signals from each configured source."""
    fetchers = (
        ("github", lambda: fetch_github_trending(limit=per_source)),
        ("arxiv", lambda: fetch_arxiv_papers(limit=per_source)),
        ("hackernews", lambda: fetch_hackernews_stories(limit=per_source)),
        ("medium", lambda: fetch_medium_blogs(limit=per_source)),
        ("huggingface", lambda: fetch_huggingface_models(limit=per_source)),
    )
    if include_releases:
        from adapters.github_releases import fetch_github_releases

        fetchers = fetchers + (
            ("github_releases", lambda: fetch_github_releases(limit=per_source)),
        )

    raw_signals: List[Dict[str, Any]] = []
    for source, fetcher in fetchers:
        print(f"Fetching {source}...")
        try:
            fetched = fetcher()
        except Exception as exc:
            print(f"  ERROR: {source} failed: {exc}")
            fetched = []

        # Medium has several feeds and can return more than per_source.
        selected = fetched[:per_source]
        print(f"  Collected {len(selected)} {source} signals")
        raw_signals.extend(selected)

    return raw_signals


def signal_key(signal: Dict[str, Any]) -> str:
    """Return the stable cross-source identifier used by annotations."""
    return f"{signal.get('source', '')}:{signal.get('id', '')}"


def validate_signals(
    signals: Iterable[Dict[str, Any]], expected_sources: Iterable[str]
) -> None:
    """Validate required fields and uniqueness after normalization."""
    errors: List[str] = []
    seen: set[str] = set()

    for index, signal in enumerate(signals):
        missing = [
            field
            for field in REQUIRED_FIELDS
            if field not in signal or signal[field] in (None, "")
        ]
        if missing:
            errors.append(f"signal[{index}] missing: {', '.join(missing)}")

        key = signal_key(signal)
        if key in seen:
            errors.append(f"duplicate identifier: {key}")
        seen.add(key)

        if not isinstance(signal.get("metadata"), dict):
            errors.append(f"signal[{index}] metadata must be an object")

    counts = Counter(signal.get("source") for signal in signals)
    missing_sources = [source for source in expected_sources if not counts[source]]
    if missing_sources:
        errors.append(f"no signals collected from: {', '.join(missing_sources)}")

    if errors:
        raise ValueError("Dataset validation failed:\n- " + "\n- ".join(errors))


def stratified_split(
    signals: List[Dict[str, Any]], dev_ratio: float, seed: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split signals by source so dev and test contain every source."""
    rng = random.Random(seed)
    by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        by_source[signal["source"]].append(signal)

    dev: List[Dict[str, Any]] = []
    test: List[Dict[str, Any]] = []

    for source in sorted(by_source):
        items = list(by_source[source])
        rng.shuffle(items)

        if len(items) < 2:
            raise ValueError(f"Need at least two signals for source: {source}")

        dev_count = round(len(items) * dev_ratio)
        dev_count = max(1, min(dev_count, len(items) - 1))
        dev.extend(items[:dev_count])
        test.extend(items[dev_count:])

    sort_key = lambda item: (item["source"], signal_key(item))
    return sorted(dev, key=sort_key), sorted(test, key=sort_key)


def make_gold_template(signals: List[Dict[str, Any]], split: str) -> Dict[str, Any]:
    """Create human-annotation records without inventing gold labels."""
    return {
        "dataset_version": "v1",
        "split": split,
        "instructions": (
            "Complete relevance_score, risk_level, breaking_changes and evidence "
            "using review before evaluating the agents."
        ),
        "records": [
            {
                "signal_id": signal_key(signal),
                "source": signal["source"],
                "title": signal["title"],
                "relevance_score": None,
                "risk_level": None,
                "breaking_changes": None,
                "evidence": None,
                "annotation_status": "pending_review",
            }
            for signal in signals
        ],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--per-source",
        type=int,
        default=12,
        help="Maximum number of signals retained per source (default: 12).",
    )
    parser.add_argument(
        "--include-releases",
        action="store_true",
        help="Include GitHub Releases as a sixth signal source.",
    )
    parser.add_argument(
        "--dev-ratio",
        type=float,
        default=0.70,
        help="Fraction assigned to development (default: 0.70).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed used for reproducible dev/test splitting (default: 42).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Output directory (default: data).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.per_source < 2:
        print("ERROR: --per-source must be at least 2.", file=sys.stderr)
        return 2
    if not 0.0 < args.dev_ratio < 1.0:
        print("ERROR: --dev-ratio must be between 0 and 1.", file=sys.stderr)
        return 2

    print("Freezing signals from configured adapters...")
    expected_sources = list(BASE_SOURCES)
    if args.include_releases:
        expected_sources.append("github_releases")

    raw_signals = collect_raw_signals(
        args.per_source, include_releases=args.include_releases
    )
    normalized = SignalCollector().collect(raw_signals)
    validate_signals(normalized, expected_sources)

    if not 60 <= len(normalized) <= 80:
        raise ValueError(
            f"Expected approximately 60-80 normalized signals; got {len(normalized)}."
        )

    dev_signals, test_signals = stratified_split(
        normalized, dev_ratio=args.dev_ratio, seed=args.seed
    )

    output_dir = args.output_dir
    write_json(output_dir / "signals_frozen.json", normalized)
    write_json(output_dir / "dev_gold.json", make_gold_template(dev_signals, "dev"))
    write_json(output_dir / "test_gold.json", make_gold_template(test_signals, "test"))

    # Keep output ASCII-compatible with Windows PowerShell encodings.
    print(f"\n[OK] Frozen {len(normalized)} normalized signals")
    print(f"[OK] Development split: {len(dev_signals)} signals")
    print(f"[OK] Test split: {len(test_signals)} signals")
    print(f"[OK] Wrote dataset files to {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
