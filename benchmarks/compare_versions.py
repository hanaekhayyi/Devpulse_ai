"""Build results/benchmark/COMPARISON.md from benchmark summaries (no LLM calls)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results" / "benchmark"

# (summary key, label, higher_is_better, format)
ROWS = [
    ("relevance.mae", "Relevance MAE", False, "{:.2f}"),
    ("relevance.spearman", "Relevance Spearman", True, "{:.3f}"),
    ("relevance.ndcg_at_10", "Relevance NDCG@10", True, "{:.3f}"),
    ("relevance.top_10_overlap", "Top-10 overlap", True, "{:.2f}"),
    ("risk.accuracy", "Risk accuracy", True, "{:.3f}"),
    ("risk.macro_f1_observed", "Risk macro-F1", True, "{:.3f}"),
    ("risk.medium_recall", "MEDIUM recall", True, "{:.3f}"),
    ("risk.category_accuracy", "Risk category accuracy", True, "{:.3f}"),
    ("risk.breaking_f1", "Breaking changes F1", True, "{:.3f}"),
    ("risk.breaking_false_positives", "Breaking false positives", False, "{:.1f}"),
    ("execution.fallback_rate", "Fallback rate", False, "{:.1%}"),
    ("execution.wall_time_s", "Wall time (s)", False, "{:.1f}"),
    ("execution.cost_usd", "Cost per run (USD)", False, "${:.4f}"),
    ("evidence.ungrounded_quote_rate", "Hallucinated evidence rate", False, "{:.1%}"),
]


def load(path: Path) -> Optional[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def cell(stat: Optional[Dict[str, Any]], fmt: str) -> str:
    if not stat:
        return "n/a"
    text = fmt.format(stat["mean"])
    if stat.get("n", 1) > 1 and stat["std"] > 0:
        text += " ± " + fmt.format(stat["std"]).lstrip("$")
    return text


def table(split: str, versions: List[str]) -> List[str]:
    summaries = {v: load(RESULTS / f"{v.replace('.', '_')}_{split}_summary.json") for v in versions}
    present = [v for v in versions if summaries[v]]
    if not present:
        return [f"_No {split.upper()} results yet._", ""]
    first = summaries[present[0]]
    lines = [
        f"Signals: {first['signal_count']} | runs per version: "
        + ", ".join(f"{v}={summaries[v]['runs']}" for v in present)
        + f" | gold: `{Path(first['gold_file']).name}` (sha256 `{first['gold_sha256'][:12]}`)",
        "",
        "| Metric | " + " | ".join(present) + " |",
        "|---|" + "---:|" * len(present),
    ]
    for key, label, higher, fmt in ROWS:
        stats = {v: summaries[v]["metrics"].get(key) for v in present}
        values = {v: s["mean"] for v, s in stats.items() if s}
        best = None
        if len(values) > 1 and len(set(round(x, 6) for x in values.values())) > 1:
            best = (max if higher else min)(values, key=values.get)
        row = []
        for v in present:
            text = cell(stats[v], fmt)
            row.append(f"**{text}**" if v == best else text)
        lines.append(f"| {label} | " + " | ".join(row) + " |")
    lines.append("")
    return lines


def injection_section() -> List[str]:
    data = load(RESULTS / "injection_dev.json")
    if not data:
        return ["_Injection benchmark not run yet._", ""]
    results = data["results"]
    versions = list(results)
    lines = [
        "| Metric (lower is better except detection) | " + " | ".join(versions) + " |",
        "|---|" + "---:|" * len(versions),
    ]
    for key, label, fmt in (
        ("downgrade_attack_success_rate", "Downgrade attack success", "{:.0%}"),
        ("risky_signals_predicted_low_under_attack", "Risky signals predicted LOW under attack", "{:.0%}"),
        ("inflation_attack_success_rate", "Inflation attack success (>= +20 pts)", "{:.0%}"),
        ("mean_relevance_inflation", "Mean relevance inflation (pts)", "{:+.1f}"),
        ("injection_detection_rate", "Injection detection rate", "{:.0%}"),
    ):
        lines.append(f"| {label} | " + " | ".join(fmt.format(results[v][key]) for v in versions) + " |")
    n_risk = len(results[versions[0]]["risk_cases"])
    n_rel = len(results[versions[0]]["relevance_cases"])
    lines += ["", f"Attacked signals: {n_risk} risky + {n_rel} low-relevance DEV signals.", ""]
    return lines


def speed_section() -> List[str]:
    seq = load(RESULTS / "v2_dev_sequential_summary.json")
    par = load(RESULTS / "v2_dev_summary.json")
    if not seq or not par:
        return ["_Sequential vs parallel timing not run yet._", ""]
    s = seq["metrics"]["execution.wall_time_s"]["mean"]
    p_runs = [json.loads((RESULTS / f).read_text(encoding="utf-8")) for f in par["run_files"]]
    uncached = [r["execution"]["duration_ms"] / 1000 for r in p_runs if r["diagnostics"].get("cache_hits", 0) == 0]
    p = sum(uncached) / len(uncached) if uncached else par["metrics"]["execution.wall_time_s"]["mean"]
    return [
        f"v2 on DEV, no cache: sequential {s:.1f}s vs concurrency {par['concurrency']} {p:.1f}s "
        f"-> **x{s / p:.1f} faster**.",
        "",
    ]


def main() -> int:
    global RESULTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", nargs="+", default=["v0", "v1.1", "v2"])
    parser.add_argument("--results-dir", type=Path, default=RESULTS)
    parser.add_argument("--title-suffix", default="")
    args = parser.parse_args()
    RESULTS = args.results_dir
    lines = [
        f"# SignalGuard: version comparison{args.title_suffix}",
        "",
        "Generated by `benchmarks/compare_versions.py` from `results/benchmark/*_summary.json`.",
        "All versions are scored against the same gold v4 files. Values are mean ± std over independent runs;",
        "the best mean in each row is in bold. v0 and v1.1 run exactly as originally implemented (no temperature",
        "setting); v2 uses temperature 0 + fixed seed.",
        "",
        "## DEV (48 signals: used during development)",
        "",
        *table("dev", args.versions),
        "## TEST (24 signals: held out, evaluated once at the end)",
        "",
        *table("test", args.versions),
        "## Prompt-injection robustness (DEV)",
        "",
        *injection_section(),
        "## Throughput",
        "",
        *speed_section(),
    ]
    out = RESULTS / "COMPARISON.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[OK] -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
