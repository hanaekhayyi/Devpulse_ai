"""One command to reproduce the whole SignalGuard evaluation.

    python benchmarks/run_all.py                 # DEV + TEST, 3 runs, injection, timing, report
    python benchmarks/run_all.py --runs 1        # quicker
    python benchmarks/run_all.py --skip-existing # resume after an interruption

Steps: v0 / v2 on DEV and TEST, prompt-injection benchmark, sequential
vs parallel timing for v2, then results/benchmark/COMPARISON.md.
Versions run in the order given (first = highest priority). On a free tier, add
--wait-on-quota to wait for the daily token quota instead of stopping.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results" / "benchmark"
PY = sys.executable


WAIT_ON_QUOTA_S = 0


def step(args: list[str]) -> None:
    while True:
        print(f"\n>>> {' '.join(args)}", flush=True)
        code = subprocess.run([PY, *args], cwd=PROJECT_ROOT).returncode
        if code == 3 and WAIT_ON_QUOTA_S:
            print(f"Quota reached: waiting {WAIT_ON_QUOTA_S // 60} min before resuming...", flush=True)
            time.sleep(WAIT_ON_QUOTA_S)
            args = resume_args(args)
            continue
        break
    if code == 3:
        print("\nDaily free quota reached. Completed steps are saved; resume later with:\n"
              "    python benchmarks/run_all.py --skip-existing --runs <same N>")
        sys.exit(3)
    if code != 0:
        sys.exit(code)


def completed_runs(stem: str) -> int:
    done = 0
    while (RESULTS / f"{stem}_run{done + 1}.json").exists():
        done += 1
    return done


def resume_args(args: list[str]) -> list[str]:
    """After a quota stop, restart a evaluate_agents step after its last saved run."""
    if "--start-run" not in args:
        return args
    version = args[args.index("--agent-version") + 1]
    split = args[args.index("--split") + 1]
    args = list(args)
    args[args.index("--start-run") + 1] = str(completed_runs(f"{version.replace('.', '_')}_{split}") + 1)
    return args


def main() -> int:
    global WAIT_ON_QUOTA_S
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--versions", nargs="+", default=["v0", "v2"])
    parser.add_argument("--splits", nargs="+", default=["dev", "test"])
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--skip-injection", action="store_true")
    parser.add_argument("--skip-timing", action="store_true")
    parser.add_argument("--wait-on-quota", action="store_true",
                        help="Free tier: when the daily quota is hit, wait and resume instead of stopping.")
    parser.add_argument("--wait-minutes", type=int, default=30)
    args = parser.parse_args()
    if args.wait_on_quota:
        WAIT_ON_QUOTA_S = args.wait_minutes * 60

    sys.path.insert(0, str(PROJECT_ROOT))
    from config import LLM_MAX_RPM, LLM_MODEL, LLM_PROVIDER

    calls = args.runs * 2 * len(args.versions) * sum({"dev": 48, "test": 24}[s] for s in args.splits)
    calls += 0 if args.skip_injection else 110
    paced = LLM_MAX_RPM > 0
    if paced and not args.skip_timing:
        print("Free-tier pacing is active: a sequential-vs-parallel timing would only measure the quota. Skipped.")
        args.skip_timing = True
    eta = f"~{calls / LLM_MAX_RPM / 60:.1f} h" if paced else "a few minutes"
    print(f"Provider {LLM_PROVIDER} / {LLM_MODEL}: about {calls} LLM calls, estimated duration {eta}.")

    for version in args.versions:  # given order = priority
        for split in args.splits:
            stem = f"{version.replace('.', '_')}_{split}"
            done = completed_runs(stem) if args.skip_existing else 0
            if done >= args.runs:
                print(f"skip {stem}: {done} run(s) already saved")
                continue
            step(["benchmarks/evaluate_agents.py", "--split", split, "--agent-version", version,
                  "--runs", str(args.runs), "--start-run", str(done + 1), "--concurrency", str(args.concurrency)])

    if not args.skip_injection and not (args.skip_existing and (RESULTS / "injection_dev.json").exists()):
        step(["benchmarks/injection_benchmark.py", "--versions", "v0", "v2",
              "--concurrency", str(args.concurrency)])

    if not args.skip_timing and not (args.skip_existing and (RESULTS / "v2_dev_sequential_summary.json").exists()):
        step(["benchmarks/evaluate_agents.py", "--split", "dev", "--agent-version", "v2", "--runs", "1",
              "--concurrency", "1", "--no-cache", "--tag", "sequential"])

    report_order = [v for v in ("v0", "v2") if v in args.versions]
    step(["benchmarks/compare_versions.py", "--versions", *report_order])
    return 0


if __name__ == "__main__":
    sys.exit(main())
