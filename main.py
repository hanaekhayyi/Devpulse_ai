"""
SignalGuard (DevPulseAI enhanced) — Multi-Agent Signal Intelligence Pipeline

Versions:
    v0    original DevPulseAI agents, sequential pipeline (kept as the comparison baseline)
    v2    Agno Workflow: structured outputs, reliability layer, injection guard,
          evidence grounding, risk triage (Router/Condition), verified LLM synthesis

Usage:
    python main.py                                   # v2, live sources
    python main.py --agent-version v0                # original behaviour
    python main.py --frozen --split dev              # reproducible run on the frozen dataset
    python main.py --no-llm-synthesis --json-out digest.json

LLM provider and models are configured in .env (see .env.example and config.py).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import LLM_API_KEY, LLM_PROVIDER, MODEL_RELEVANCE, MODEL_RISK, MODEL_SYNTHESIS

from adapters.arxiv import fetch_arxiv_papers
from adapters.github import fetch_github_trending
from adapters.github_releases import fetch_github_releases
from adapters.hackernews import fetch_hackernews_stories
from adapters.huggingface import fetch_huggingface_models
from adapters.medium import fetch_medium_blogs
from agents import RelevanceAgent, RiskAgent, SignalCollector, SynthesisAgent

# Public helpers reused by the web app
DEFAULT_SIGNAL_LIMIT = 5
FROZEN_SIGNALS = Path(__file__).resolve().parent / "data" / "benchmark" / "signals_frozen.json"


def collect_signals(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Collect raw signals from every source (pure data aggregation, no LLM)."""
    fetch_limit = limit if limit is not None else DEFAULT_SIGNAL_LIMIT
    print(f"\n📡 Collecting signals (limit: {fetch_limit} per source)...")
    sources = [
        ("GitHub trending repos", lambda: fetch_github_trending(limit=fetch_limit)),
        ("ArXiv papers", lambda: fetch_arxiv_papers(limit=fetch_limit)),
        ("HackerNews stories", lambda: fetch_hackernews_stories(limit=fetch_limit)),
        ("Medium blogs", lambda: fetch_medium_blogs(limit=min(fetch_limit, 3))),
        ("HuggingFace models", lambda: fetch_huggingface_models(limit=fetch_limit)),
        ("GitHub releases", lambda: fetch_github_releases(limit=fetch_limit)),
    ]
    signals: List[Dict[str, Any]] = []
    for label, fetch in sources:
        try:
            batch = fetch()
        except Exception as exc:  # noqa: BLE001 — one failing source must not stop the pipeline
            print(f"  ⚠️  {label}: {exc}")
            continue
        print(f"  → {label}: {len(batch)}")
        signals.extend(batch)
    print(f"  ✓ Collected {len(signals)} raw signals")
    return signals


# --------------------------------------------------------------------------- original pipeline (v0)

def run_legacy(version: str, raw_signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    relevance, risk = RelevanceAgent(), RiskAgent()

    collector = SignalCollector()
    normalized = collector.collect(raw_signals)
    print(f"\n🔄 {collector.summarize_collection(normalized)}")
    print("\n📊 Scoring relevance...")
    scored = relevance.score_batch(normalized)
    print("⚠️  Assessing risks...")
    assessed = risk.assess_batch(scored)
    print("📋 Generating digest...")
    digest = SynthesisAgent().synthesize(assessed)
    digest["synthesis"] = {"mode": "deterministic (v0 SynthesisAgent)"}
    fallbacks = sum(bool(s.get("relevance", {}).get("used_fallback")) + bool(s.get("risk", {}).get("used_fallback"))
                    for s in assessed)
    return {"digest": digest, "fallbacks": fallbacks, "assessed": assessed}


# --------------------------------------------------------------------------- v2 (Agno Workflow)

def run_v2(args: argparse.Namespace) -> Dict[str, Any]:
    from agents.v2 import RelevanceAgentV2, ResponseCache, RiskAgentV2
    from agents.v2.synthesis import SynthesisAgentV2
    from pipeline.workflow import build_workflow, run_workflow

    cache = ResponseCache()
    workflow = build_workflow(
        RelevanceAgentV2(cache=cache),
        RiskAgentV2(cache=cache),
        SynthesisAgentV2(cache=cache),
        collect_live=collect_signals,
    )
    options: Dict[str, Any] = {
        "llm_synthesis": not args.no_llm_synthesis,
        "concurrency": args.concurrency,
        "limit_per_source": args.limit,
    }
    if args.frozen:
        options.update(frozen_path=str(FROZEN_SIGNALS), split=args.split, max_signals=args.max_signals)
    return run_workflow(workflow, **options)


# --------------------------------------------------------------------------- output

def print_digest(version: str, result: Dict[str, Any], elapsed: float) -> None:
    digest = result["digest"]
    print("\n" + "=" * 64)
    print(f"📄 INTELLIGENCE DIGEST — {version}")
    print("=" * 64)
    print(f"📦 Signals: {digest.get('total_signals')} | fallbacks: {result.get('fallbacks', 0)} | "
          f"time: {elapsed:.1f}s")
    triage = result.get("triage")
    if triage:
        total = len(triage["risk_llm"]) + len(triage["risk_fast_path"])
        print(f"🔀 Risk triage: {len(triage['risk_llm'])}/{total} signals sent to the LLM, "
              f"{len(triage['risk_fast_path'])} handled by the deterministic fast path")
    synthesis = digest.get("synthesis", {})
    print(f"🧠 Synthesis: {synthesis.get('mode')}"
          + (f" (fallback: {synthesis.get('fallback_reason')})" if synthesis.get("used_fallback") else "")
          + (f" | rejected ids: {synthesis['rejected_signal_ids']}" if synthesis.get("rejected_signal_ids") else ""))
    print(f"\n📝 {digest.get('executive_summary')}")

    print("\n🎯 Top priority signals:")
    for i, s in enumerate(digest.get("priority_signals", [])[:5], 1):
        risk = s.get("risk", {})
        print(f"   {i}. [{s.get('source')}] {str(s.get('title'))[:60]}")
        print(f"      relevance {s.get('relevance', {}).get('score', '?')} | risk {risk.get('risk_level', '?')}"
              f"/{risk.get('risk_category', '-')}" + (" | BREAKING" if risk.get("breaking_changes") else ""))

    if digest.get("key_signals") and isinstance(digest["key_signals"][0], dict):
        print("\n🔑 Why it matters:")
        for item in digest["key_signals"][:5]:
            print(f"   • {str(item.get('title'))[:55]}: {item.get('why_it_matters')}")

    print("\n💡 Recommendations:")
    for rec in digest.get("recommendations", []):
        if isinstance(rec, dict):
            ids = rec.get("signal_ids") or []
            print(f"   • {rec['action']}" + (f"  [{len(ids)} signal(s)]" if ids else ""))
        else:
            print(f"   • {rec}")
    print("=" * 64)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SignalGuard signal intelligence pipeline")
    parser.add_argument("--agent-version", choices=("v0", "v2"), default="v2")
    parser.add_argument("--limit", type=int, default=DEFAULT_SIGNAL_LIMIT, help="Live mode: signals per source.")
    parser.add_argument("--frozen", action="store_true", help="Use the frozen dataset instead of live sources.")
    parser.add_argument("--split", choices=("dev", "test"), default=None, help="Frozen mode: restrict to a split.")
    parser.add_argument("--max-signals", type=int, default=None, help="Frozen mode: cap the number of signals.")
    parser.add_argument("--no-llm-synthesis", action="store_true", help="v2: Python-only digest.")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args(argv)


def run_pipeline(argv: Optional[List[str]] = None) -> Dict[str, Any]:
    args = parse_args(argv)
    print("=" * 64)
    print(f"🛡️  SignalGuard — {args.agent_version} | provider: {LLM_PROVIDER}")
    print(f"   models: relevance={MODEL_RELEVANCE} | risk={MODEL_RISK} | synthesis={MODEL_SYNTHESIS}")
    print("=" * 64)
    if not LLM_API_KEY:
        print("⚠️  No API key for the selected provider: agents will use their fallbacks.")

    started = time.perf_counter()
    if args.agent_version == "v2":
        result = run_v2(args)
    else:
        if args.frozen:
            from pipeline.workflow import load_frozen

            raw = load_frozen(FROZEN_SIGNALS, args.split, args.max_signals)
        else:
            raw = collect_signals(args.limit)
        result = run_legacy(args.agent_version, raw)
    elapsed = time.perf_counter() - started
    print_digest(args.agent_version, result, elapsed)

    if args.json_out:
        args.json_out.write_text(json.dumps(result["digest"], ensure_ascii=False, indent=2, default=str),
                                 encoding="utf-8")
        print(f"💾 Digest written to {args.json_out}")
    return result["digest"]


if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        sys.exit(130)
    except BaseException as exc:  # QuotaExhausted derives from BaseException on purpose
        if type(exc).__name__ != "QuotaExhausted":
            raise
        print(f"\n⛔ Provider quota exhausted: {exc}\n"
              "   Retry later, or select another model for this run, e.g. LLM_MODEL_RELEVANCE=<model>.",
              file=sys.stderr)
        sys.exit(3)
