"""Audit v4 risk taxonomy without changing any annotation."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "benchmark"
OUTPUT = ROOT / "results" / "gold_v4_audit.json"


def audit(split: str) -> dict:
    path = DATASET / f"{split}_gold_annotated_v4.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    warnings = []
    for record in document["records"]:
        level = str(record.get("risk_level", "")).upper()
        category = str(record.get("risk_category", "")).upper()
        breaking = record.get("breaking_changes")
        if category == "SECURITY" and level == "LOW":
            warnings.append({"signal_id": record["signal_id"], "type": "LOW_SECURITY"})
        if category == "NONE" and level not in {"LOW"}:
            warnings.append({"signal_id": record["signal_id"], "type": "ELEVATED_NONE"})
        if category == "COMPATIBILITY" and breaking is not True:
            warnings.append({"signal_id": record["signal_id"], "type": "COMPATIBILITY_NOT_BREAKING"})
        if category == "SUSPICION" and level not in {"MEDIUM", "HIGH"}:
            warnings.append({"signal_id": record["signal_id"], "type": "SUSPICION_LEVEL"})
    return {
        "split": split,
        "record_count": len(document["records"]),
        "risk_level_counts": _counts(document["records"], "risk_level"),
        "risk_category_counts": _counts(document["records"], "risk_category"),
        "breaking_changes_true": sum(record.get("breaking_changes") is True for record in document["records"]),
        "warnings": warnings,
    }


def _counts(records: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(key, "MISSING")).upper()
        counts[value] = counts.get(value, 0) + 1
    return counts


if __name__ == "__main__":
    report = {"dataset_version": "v4-reviewed-risk-taxonomy", "splits": [audit("dev"), audit("test")]}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
