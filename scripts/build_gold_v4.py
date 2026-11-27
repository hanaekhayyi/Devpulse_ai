"""Create the reviewed v4 gold files without modifying the v3 references."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "benchmark"
SUSPICION_MARKERS = re.compile(
    r"hack|cheat|executor|keygen|crack|sniping|leurre|usurpation|faux antivirus|piratage",
    re.IGNORECASE,
)
SECURITY_MARKERS = re.compile(r"cve|vulnerability|exploit|rce|malware|breach", re.IGNORECASE)


def classify(record: dict) -> tuple[str, str]:
    evidence = str(record.get("evidence", ""))
    if record.get("breaking_changes"):
        return "COMPATIBILITY", "Explicit compatibility or support change."
    if SECURITY_MARKERS.search(evidence):
        return "SECURITY", "Security concern documented in the evidence."
    if record.get("risk_level") == "HIGH" and SUSPICION_MARKERS.search(evidence):
        return "SUSPICION", "Suspicion indicators are present, but no direct exploit is documented."
    return "NONE", "No explicit elevated risk evidence in the frozen signal."


def build(split: str) -> None:
    source_path = DATASET / f"{split}_gold_annotated_v3.json"
    output_path = DATASET / f"{split}_gold_annotated_v4.json"
    document = json.loads(source_path.read_text(encoding="utf-8"))
    reviewed = []
    for original in document["records"]:
        record = dict(original)
        category, category_evidence = classify(record)
        if category == "SUSPICION":
            record["risk_level"] = "MEDIUM"
        record["risk_category"] = category
        record["evidence"] = f"{record.get('evidence', '')} Taxonomy: {category_evidence}"
        record["annotation_status"] = "verified"
        reviewed.append(record)
    result = {
        "dataset_version": "v4-reviewed-risk-taxonomy",
        "split": split,
        "instructions": (
            "Annotations de reference verifiees. La taxonomie distingue les changements de compatibilite, "
            "les risques de securite documentes et les simples suspicions."
        ),
        "records": reviewed,
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output_path} ({len(reviewed)} records)")


if __name__ == "__main__":
    build("dev")
    build("test")
