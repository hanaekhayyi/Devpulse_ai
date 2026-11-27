"""Re-score saved benchmark runs against another gold version (no LLM call).

    python scripts/rescore_on_gold.py --gold-version v4_1

Predictions are reused as-is; only the reference labels change. Output goes to
results/benchmark/gold_<version>/ with the same file names, then compare_versions.py
can build a COMPARISON.md for that reference.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.metrics import evaluate_relevance, evaluate_risk  # noqa: E402
from benchmarks.evaluate_agents import load_json, sha256_file, summarise  # noqa: E402

RESULTS = ROOT / "results" / "benchmark"
DATASET = ROOT / "data" / "benchmark"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-version", default="v4_1")
    parser.add_argument("--results-dir", type=Path, default=RESULTS)
    args = parser.parse_args()
    results = args.results_dir
    out_dir = results / f"gold_{args.gold_version}"
    out_dir.mkdir(parents=True, exist_ok=True)

    for summary_path in sorted(results.glob("*_summary.json")):
        summary = load_json(summary_path)
        split = summary["split"]
        gold_path = DATASET / f"{split}_gold_annotated_{args.gold_version}.json"
        gold = {r["signal_id"]: r for r in load_json(gold_path)["records"]}
        runs = []
        for name in summary["run_files"]:
            run = load_json(results / name)
            for record in run["records"]:
                g = gold[record["signal_id"]]
                record["gold"] = {
                    "relevance_score": g["relevance_score"],
                    "risk_level": g["risk_level"],
                    "breaking_changes": g["breaking_changes"],
                    "risk_category": g.get("risk_category"),
                }
            run["dataset"]["gold_file"] = str(gold_path.relative_to(ROOT))
            run["dataset"]["gold_sha256"] = sha256_file(gold_path)
            run["metrics"] = {"relevance": evaluate_relevance(run["records"]), "risk": evaluate_risk(run["records"])}
            run["rescored_offline"] = True
            (out_dir / name).write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            runs.append(run)
        summary.update(
            gold_file=str(gold_path.relative_to(ROOT)), gold_sha256=sha256_file(gold_path),
            metrics=summarise(runs), rescored_offline=True,
        )
        (out_dir / summary_path.name).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8")
        print(f"{summary_path.name} -> {out_dir.name}/")
    injection = results / "injection_dev.json"
    if injection.exists():
        (out_dir / injection.name).write_text(injection.read_text(encoding="utf-8"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
