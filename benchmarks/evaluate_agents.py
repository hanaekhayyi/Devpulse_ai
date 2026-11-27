"""Run the original DevPulseAI (v0) or SignalGuard v2 on a frozen dataset.

All versions are evaluated against the SAME reference (gold v4 by default).
All versions share one gold file, so their metrics are directly comparable.

Examples:
    python benchmarks/evaluate_agents.py --split dev --agent-version v2
    python benchmarks/evaluate_agents.py --split test --agent-version v0 --runs 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.metrics import evaluate_relevance, evaluate_risk  # noqa: E402
from config import LLM_MODEL, LLM_PROVIDER, OPENROUTER_BASE_URL  # noqa: E402

DEFAULT_DATASET_DIR = PROJECT_ROOT / "data" / "benchmark"
DEFAULT_GOLD_VERSION = "v4"
VERSIONS = ("v0", "v2")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_signal_index(signals: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    index = {f"{s.get('source', '')}:{s.get('id', '')}": s for s in signals}
    if len(index) != len(signals):
        raise ValueError("signals_frozen.json contains duplicate source:id keys")
    return index


def rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def gold_path_for(dataset_dir: Path, split: str, gold_version: str = DEFAULT_GOLD_VERSION) -> Path:
    return dataset_dir / f"{split}_gold_annotated_{gold_version}.json"


# --------------------------------------------------------------------------- agents

def make_agent_factories(version: str, use_cache: bool) -> Tuple[Callable[[], Any], Callable[[], Any], bool]:
    """Return (relevance_factory, risk_factory, thread_safe).

    Legacy agents keep one Agno Agent per instance, so they get one instance per
    worker thread. v2 builds a fresh Agno Agent per call and is thread-safe.
    """
    if version == "v2":
        from agents.v2 import RelevanceAgentV2, ResponseCache, RiskAgentV2

        cache = ResponseCache() if use_cache else None
        relevance, risk = RelevanceAgentV2(cache=cache), RiskAgentV2(cache=cache)
        return (lambda: relevance), (lambda: risk), True
    from agents.relevance_agent import RelevanceAgent
    from agents.risk_agent import RiskAgent

    return RelevanceAgent, RiskAgent, False


def pace_legacy_agent(wrapper: Any) -> Any:
    """Route a legacy agent's Agno calls through the shared rate limiter.

    Free tiers answer HTTP 429 when the per-minute quota is exceeded. Legacy
    agents would turn that into a heuristic fallback and be scored on the
    provider's quota instead of their own quality, so the harness paces their
    calls and retries quota errors. Prompts and parsing are left unchanged.
    """
    from agents.v2.ratelimit import QuotaExhausted, global_limiter

    inner = getattr(wrapper, "agent", None)
    if inner is None or getattr(inner, "_signalguard_paced", False):
        return wrapper
    original_run = inner.run
    model_id = getattr(getattr(inner, "model", None), "id", "") or ""

    def paced_run(*args: Any, **kwargs: Any) -> Any:
        for attempt in range(5):
            global_limiter(model_id).acquire()
            response = original_run(*args, **kwargs)
            failed = "error" in str(getattr(response, "status", "")).lower()
            # A provider-side error (quota, 5xx, timeout) is not a model answer: retry it.
            # Unparseable answers come back with status "completed" and are left to the agent.
            if failed and attempt < 4:
                time.sleep(min(60.0, 10.0 * (2**attempt)))
                continue
            if failed:
                raise QuotaExhausted(f"{model_id}: {str(getattr(response, 'content', ''))[:200]}")
            return response
        return response

    object.__setattr__(inner, "run", paced_run)
    object.__setattr__(inner, "_signalguard_paced", True)
    return wrapper


class AgentPool:
    def __init__(self, factory: Callable[[], Any], thread_safe: bool):
        self.factory = factory
        self.thread_safe = thread_safe
        self._shared = factory() if thread_safe else None
        self._local = threading.local()

    def get(self) -> Any:
        if self.thread_safe:
            return self._shared
        if not hasattr(self._local, "agent"):
            self._local.agent = pace_legacy_agent(self.factory())
        return self._local.agent


# --------------------------------------------------------------------------- evaluation

def evaluate_one(signal: Dict[str, Any], gold: Dict[str, Any], relevance_agent: Any, risk_agent: Any,
                 cache_salt: str) -> Dict[str, Any]:
    kwargs = {"cache_salt": cache_salt} if getattr(relevance_agent, "version", None) == "v2" else {}

    t0 = time.perf_counter()
    relevance = relevance_agent.score(signal, **kwargs)
    relevance_ms = round((time.perf_counter() - t0) * 1000, 2)
    t1 = time.perf_counter()
    risk = risk_agent.assess(signal, **kwargs)
    risk_ms = round((time.perf_counter() - t1) * 1000, 2)

    record: Dict[str, Any] = {
        "signal_id": gold["signal_id"],
        "source": signal["source"],
        "title": signal["title"],
        "gold": {
            "relevance_score": gold["relevance_score"],
            "risk_level": gold["risk_level"],
            "breaking_changes": gold["breaking_changes"],
            "risk_category": gold.get("risk_category"),
        },
        "predictions": {
            "relevance_score": relevance.get("score"),
            "relevance_reasoning": relevance.get("reasoning"),
            "relevance_rubric": {
                k: relevance.get(k)
                for k in ("novelty", "technical_relevance", "applicability", "timeliness")
                if k in relevance
            },
            "risk_level": risk.get("risk_level"),
            "risk_category": risk.get("risk_category"),
            "concerns": risk.get("concerns", []),
            "evidence": risk.get("evidence", []),
            "breaking_changes": risk.get("breaking_changes"),
            "evidence_strength": risk.get("evidence_strength"),
        },
        "fallback": {
            "relevance": bool(relevance.get("used_fallback", False)),
            "risk": bool(risk.get("used_fallback", False)),
            "relevance_reason": relevance.get("fallback_reason"),
            "risk_reason": risk.get("fallback_reason"),
        },
        "latency_ms": {"relevance": relevance_ms, "risk": risk_ms},
    }
    if "usage" in risk:
        record["v2"] = {
            "relevance_adjustments": relevance.get("adjustments", []),
            "risk_adjustments": risk.get("adjustments", []),
            "llm_view": risk.get("llm_view"),
            "grounding": risk.get("grounding"),
            "rejected_evidence": risk.get("rejected_evidence", []),
            "profile": risk.get("profile"),
            "usage": {"relevance": relevance.get("usage"), "risk": risk.get("usage")},
        }
    return record


def diagnostics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    v2 = [r["v2"] for r in records if "v2" in r]
    if not v2:
        return {"available": False}
    usages = [u for r in v2 for u in r["usage"].values() if u]
    quotes = {"exact": 0, "fuzzy": 0, "ungrounded": 0}
    for r in v2:
        for k, v in (r.get("grounding") or {}).items():
            quotes[k] += v
    total_quotes = sum(quotes.values())
    return {
        "available": True,
        "llm_calls": len(usages),
        "cache_hits": sum(u["cache_hit"] for u in usages),
        "retries": sum(max(0, u["attempts"] - 1) for u in usages if not u["cache_hit"]),
        "input_tokens": sum(u["input_tokens"] for u in usages),
        "output_tokens": sum(u["output_tokens"] for u in usages),
        "cost_usd": round(sum(u["cost_usd"] for u in usages), 6),
        "evidence_quotes": quotes,
        "ungrounded_quote_rate": quotes["ungrounded"] / total_quotes if total_quotes else None,
        "risk_rule_interventions": sum(
            1 for r in v2 if any(not a.startswith("rejected") for a in r["risk_adjustments"])
        ),
        "relevance_caps": sum(1 for r in v2 if r["relevance_adjustments"]),
        "lure_signals_detected": sum(1 for r in v2 if (r.get("profile") or {}).get("is_lure")),
        "injection_signals_detected": sum(1 for r in v2 if (r.get("profile") or {}).get("injection_detected")),
    }


def load_checkpoint(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if not path or not path.exists():
        return {}
    records: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # torn last line after an interruption
        records[record["signal_id"]] = record
    return records


def run_once(version: str, gold_records: List[Dict[str, Any]], signal_index: Dict[str, Dict[str, Any]],
             concurrency: int, use_cache: bool, run_index: int,
             checkpoint: Optional[Path] = None) -> Tuple[List[Dict[str, Any]], float]:
    """Evaluate every signal once. Completed signals are appended to ``checkpoint``
    so a run interrupted by a quota stop resumes without re-spending tokens."""
    rel_factory, risk_factory, thread_safe = make_agent_factories(version, use_cache)
    rel_pool, risk_pool = AgentPool(rel_factory, thread_safe), AgentPool(risk_factory, thread_safe)
    salt = f"run{run_index}"
    saved = load_checkpoint(checkpoint)
    if saved:
        print(f"  resuming run {run_index}: {len(saved)} signal(s) already done", flush=True)
    done = [len(saved)]
    lock = threading.Lock()

    def task(gold: Dict[str, Any]) -> Dict[str, Any]:
        if gold["signal_id"] in saved:
            return saved[gold["signal_id"]]
        signal = signal_index.get(gold["signal_id"])
        if signal is None:
            raise ValueError(f"Annotation references unknown signal: {gold['signal_id']}")
        record = evaluate_one(signal, gold, rel_pool.get(), risk_pool.get(), salt)
        with lock:
            done[0] += 1
            if checkpoint:
                with checkpoint.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"  [{version} run {run_index}] {done[0]}/{len(gold_records)} {signal['title'][:70]}", flush=True)
        return record

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        records = list(pool.map(task, gold_records))
    return records, round((time.perf_counter() - started) * 1000, 2)


KEY_METRICS = {
    "relevance.mae": ("relevance", "mean_absolute_error"),
    "relevance.spearman": ("relevance", "spearman"),
    "relevance.ndcg_at_10": ("relevance", "ndcg_at_10"),
    "relevance.top_10_overlap": ("relevance", "top_10_overlap"),
    "risk.accuracy": ("risk", "risk_level", "accuracy"),
    "risk.macro_f1_observed": ("risk", "risk_level", "macro_f1_observed_classes"),
    "risk.medium_recall": ("risk", "risk_level", "per_class", "MEDIUM", "recall"),
    "risk.category_accuracy": ("risk", "risk_category", "accuracy"),
    "risk.breaking_f1": ("risk", "breaking_changes", "f1"),
    "risk.breaking_false_positives": ("risk", "breaking_changes", "false_positives"),
}


def dig(data: Dict[str, Any], path: Tuple[str, ...]) -> Optional[float]:
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data if isinstance(data, (int, float)) else None


def summarise(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    series: Dict[str, List[float]] = {}
    for name, path in KEY_METRICS.items():
        series[name] = [v for v in (dig(r["metrics"], path) for r in runs) if v is not None]
    series["execution.wall_time_s"] = [r["execution"]["duration_ms"] / 1000 for r in runs]
    series["execution.fallback_rate"] = [
        (r["execution"]["relevance_fallbacks"] + r["execution"]["risk_fallbacks"]) / (2 * r["dataset"]["signal_count"])
        for r in runs
    ]
    costs = [r["diagnostics"].get("cost_usd") for r in runs if r["diagnostics"].get("available")]
    if costs:
        series["execution.cost_usd"] = costs
        series["evidence.ungrounded_quote_rate"] = [
            r["diagnostics"]["ungrounded_quote_rate"] for r in runs
            if r["diagnostics"].get("ungrounded_quote_rate") is not None
        ]
    for name, values in series.items():
        if values:
            summary[name] = {
                "mean": statistics.fmean(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
                "n": len(values),
            }
    return summary


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--agent-version", choices=VERSIONS, default="v0")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--gold-version", default=DEFAULT_GOLD_VERSION)
    parser.add_argument("--gold-file", type=Path, default=None, help="Explicit gold file (overrides --gold-version).")
    parser.add_argument("--runs", type=int, default=1, help="Independent repetitions, reported as mean ± std.")
    parser.add_argument("--start-run", type=int, default=1,
                        help="Resume: reuse saved runs 1..N-1 (same version/split) and execute runs N..--runs.")
    parser.add_argument("--concurrency", type=int, default=6, help="Parallel signals (1 = sequential).")
    parser.add_argument("--no-cache", action="store_true", help="v2 only: bypass the response cache.")
    parser.add_argument("--max-signals", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "results" / "benchmark")
    parser.add_argument("--tag", default="", help="Suffix added to output file names.")
    parser.add_argument("--allow-unverified", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    return parser.parse_args(argv)


def preflight() -> None:
    """One tiny request before a long benchmark: fail fast with a clear message."""
    import httpx

    from config import LLM_API_KEY, LLM_BASE_URL, LLM_MAX_RPM, LLM_MODEL, LLM_PROVIDER, MODEL_RISK

    model = LLM_MODEL if LLM_PROVIDER != "openrouter" else MODEL_RISK
    if not LLM_API_KEY:
        raise SystemExit(f"PREFLIGHT FAILED: no API key for provider '{LLM_PROVIDER}' (see .env.example).")
    print(f"Provider: {LLM_PROVIDER} | model: {model} | pacing: {LLM_MAX_RPM or 'unlimited'} req/min")
    for attempt in range(3):
        response = httpx.post(
            f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={"model": model, "max_tokens": 5,
                  "messages": [{"role": "system", "content": "Reply OK."}, {"role": "user", "content": "ping"}]},
            timeout=60,
        )
        if response.status_code == 200:
            return
        quota = response.headers.get("x-ratelimit-limit-req-minute")
        if response.status_code == 429 and quota == "0":
            raise SystemExit(f"PREFLIGHT FAILED: model '{model}' has a quota of 0 requests/minute on this plan. "
                             "Choose another model with LLM_MODEL.")
        if response.status_code == 429 and attempt < 2:
            time.sleep(35)
            continue
        raise SystemExit(f"PREFLIGHT FAILED: HTTP {response.status_code}: {response.text[:300]}")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.skip_preflight:
        preflight()
    signals_path = args.dataset_dir / "signals_frozen.json"
    gold_path = args.gold_file or gold_path_for(args.dataset_dir, args.split, args.gold_version)
    for path in (signals_path, gold_path):
        if not path.exists():
            raise FileNotFoundError(path)

    signal_index = build_signal_index(load_json(signals_path))
    gold_records = list(load_json(gold_path)["records"])
    unverified = [r for r in gold_records if r.get("annotation_status") != "verified"]
    if unverified and not args.allow_unverified:
        raise ValueError(f"{len(unverified)} annotations are not verified. Use --allow-unverified to override.")
    if args.max_signals is not None:
        gold_records = gold_records[: args.max_signals]

    stem = f"{args.agent_version.replace('.', '_')}_{args.split}{('_' + args.tag) if args.tag else ''}"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    runs: List[Dict[str, Any]] = []
    for previous in range(1, args.start_run):
        previous_path = args.output_dir / f"{stem}_run{previous}.json"
        if not previous_path.exists():
            raise FileNotFoundError(f"--start-run {args.start_run} needs {previous_path}")
        runs.append(load_json(previous_path))
        print(f"reusing {previous_path.name}")
    for run_index in range(args.start_run, args.runs + 1):
        print(f"\n=== {args.agent_version} | {args.split} | run {run_index}/{args.runs} | concurrency {args.concurrency}")
        checkpoint = args.output_dir / f"{stem}_run{run_index}.partial.jsonl"
        resumed = checkpoint.exists()
        records, duration_ms = run_once(
            args.agent_version, gold_records, signal_index, args.concurrency, not args.no_cache, run_index,
            checkpoint=checkpoint,
        )
        relevance_fallbacks = sum(r["fallback"]["relevance"] for r in records)
        risk_fallbacks = sum(r["fallback"]["risk"] for r in records)
        output = {
            "benchmark_version": args.agent_version,
            "run_index": run_index,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "split": args.split,
            "dataset": {
                "signals_file": rel(signals_path),
                "gold_file": rel(gold_path),
                "signals_sha256": sha256_file(signals_path),
                "gold_sha256": sha256_file(Path(gold_path)),
                "signal_count": len(records),
            },
            "models": {"provider": LLM_PROVIDER, "model": LLM_MODEL or "per-agent env", "base_url": OPENROUTER_BASE_URL},
            "execution": {
                "duration_ms": duration_ms,
                "resumed_from_checkpoint": resumed,  # duration then covers only the resumed part
                "concurrency": args.concurrency,
                "api_calls_requested": len(records) * 2,
                "relevance_fallbacks": relevance_fallbacks,
                "risk_fallbacks": risk_fallbacks,
            },
            "metrics": {"relevance": evaluate_relevance(records), "risk": evaluate_risk(records)},
            "diagnostics": diagnostics(records),
            "records": records,
        }
        run_path = args.output_dir / f"{stem}_run{run_index}.json"
        run_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checkpoint.unlink(missing_ok=True)
        runs.append(output)
        m = output["metrics"]
        print(
            f"[OK] run {run_index}: MAE={m['relevance']['mean_absolute_error']:.2f} "
            f"Spearman={m['relevance']['spearman']:.3f} "
            f"RiskAcc={m['risk']['risk_level']['accuracy']:.3f} "
            f"time={duration_ms / 1000:.1f}s -> {rel(run_path)}"
        )

    summary = {
        "agent_version": args.agent_version,
        "split": args.split,
        "gold_file": runs[0]["dataset"]["gold_file"],
        "gold_sha256": runs[0]["dataset"]["gold_sha256"],
        "signal_count": runs[0]["dataset"]["signal_count"],
        "runs": len(runs),
        "concurrency": args.concurrency,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": summarise(runs),
        "run_files": [f"{stem}_run{i}.json" for i in range(1, len(runs) + 1)],
    }
    summary_path = args.output_dir / f"{stem}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] summary -> {rel(summary_path)}")
    return 0


if __name__ == "__main__":
    from agents.v2.ratelimit import QuotaExhausted

    try:
        raise SystemExit(main())
    except QuotaExhausted as exc:
        print(f"\nQUOTA EXHAUSTED: {exc}\nNothing was saved for this version/split. "
              "Resume later with: python benchmarks/run_all.py --skip-existing", file=sys.stderr)
        raise SystemExit(3)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
