"""Build gold v4.1 from v4 by fixing the inconsistencies flagged by audit_gold_v4.py.

Minimal-change rule (decided from the label/evidence text only, never from a
model prediction):
- the annotated ``risk_level`` is the annotator's judgement and is kept;
- ``risk_category`` is made consistent with that level and with the free-text
  evidence written by the annotator.

Cases:
- LOW_SECURITY: evidence mentions no security problem -> category NONE.
- ELEVATED_NONE with ``custom_code`` / ``trust_remote_code`` -> SECURITY
  (remote code executed at load time is a security exposure, not proven malicious).
- ELEVATED_NONE on a suspicious repository profile -> SUSPICION.

v4 is left untouched; every change is recorded in ``corrections``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "benchmark"

CORRECTIONS = {
    # signal_id: (new_category, reason)
    "hackernews:42174829": ("NONE", "LOW_SECURITY: evidence describes a RAG library, no security issue"),
    "hackernews:44649115": ("NONE", "LOW_SECURITY: evidence describes an e-commerce product, no security issue"),
    "hackernews:48819808": ("NONE", "LOW_SECURITY: evidence describes a local-first app, no security issue"),
    "hackernews:42063346": ("NONE", "LOW_SECURITY: evidence describes an AI IDE, no security issue"),
    "hackernews:45029254": ("NONE", "LOW_SECURITY: evidence describes a Python CLI, no security issue"),
    "huggingface:deepseek-ai/DeepSeek-R1": (
        "SECURITY", "ELEVATED_NONE: MEDIUM justified by custom_code / trust_remote_code (remote code execution exposure)"),
    "huggingface:moonshotai/Kimi-K3": (
        "SECURITY", "ELEVATED_NONE: MEDIUM justified by custom_code / trust_remote_code (remote code execution exposure)"),
    "github:1469445489": (
        "SUSPICION", "ELEVATED_NONE: MEDIUM justified by an unclear, game-like repository profile (indicator, no proof)"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    applied = 0
    for split in ("dev", "test"):
        source = DATASET / f"{split}_gold_annotated_v4.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        out = copy.deepcopy(data)
        out["dataset_version"] = "v4.1-consistency-fixes"
        out["derived_from"] = {"file": source.name, "sha256": sha256(source)}
        out["corrections"] = []
        for record in out["records"]:
            fix = CORRECTIONS.get(record["signal_id"])
            if not fix:
                continue
            new_category, reason = fix
            out["corrections"].append({
                "signal_id": record["signal_id"],
                "title": record["title"],
                "field": "risk_category",
                "old": record["risk_category"],
                "new": new_category,
                "risk_level_kept": record["risk_level"],
                "reason": reason,
            })
            record["risk_category"] = new_category
            applied += 1
        target = DATASET / f"{split}_gold_annotated_v4_1.json"
        target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{target.name}: {len(out['corrections'])} correction(s)")
    if applied != len(CORRECTIONS):
        raise SystemExit(f"Expected {len(CORRECTIONS)} corrections, applied {applied}: check signal ids.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
