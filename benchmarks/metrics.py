"""Dependency-free benchmark metrics.

NDCG uses graded relevance normalized to [0, 1] before applying the standard
gain ``2**relevance - 1``. This keeps a 0-100 annotation scale numerically
meaningful and avoids an exponential gain of ``2**100``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence


RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _rankdata(values: Sequence[float]) -> List[float]:
    """Average ranks for ties, equivalent to scipy.stats.rankdata average."""
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        average_rank = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            ranks[indexed[position][0]] = average_rank
        cursor = end
    return ranks


def spearman_correlation(expected: Sequence[float], predicted: Sequence[float]) -> float | None:
    if len(expected) != len(predicted) or len(expected) < 2:
        return None
    expected_ranks = _rankdata(expected)
    predicted_ranks = _rankdata(predicted)
    expected_mean = sum(expected_ranks) / len(expected_ranks)
    predicted_mean = sum(predicted_ranks) / len(predicted_ranks)
    numerator = sum(
        (a - expected_mean) * (b - predicted_mean)
        for a, b in zip(expected_ranks, predicted_ranks)
    )
    left = sum((a - expected_mean) ** 2 for a in expected_ranks)
    right = sum((b - predicted_mean) ** 2 for b in predicted_ranks)
    denominator = math.sqrt(left * right)
    return numerator / denominator if denominator else 1.0


def ndcg_at_k_legacy(expected: Sequence[float], predicted: Sequence[float], k: int = 10) -> float | None:
    if len(expected) != len(predicted) or not expected:
        return None
    k = min(k, len(expected))

    predicted_order = sorted(range(len(predicted)), key=lambda i: predicted[i], reverse=True)
    ideal_order = sorted(range(len(expected)), key=lambda i: expected[i], reverse=True)

    def dcg(order: Sequence[int]) -> float:
        return sum(
            (2 ** expected[index] - 1) / math.log2(position + 2)
            for position, index in enumerate(order[:k])
        )

    ideal = dcg(ideal_order)
    return dcg(predicted_order) / ideal if ideal else 1.0


def ndcg_at_k(expected: Sequence[float], predicted: Sequence[float], k: int = 10) -> float | None:
    """NDCG@k for 0-100 graded scores with normalized exponential gain."""
    if len(expected) != len(predicted) or not expected:
        return None
    k = min(k, len(expected))
    predicted_order = sorted(range(len(predicted)), key=lambda i: predicted[i], reverse=True)
    ideal_order = sorted(range(len(expected)), key=lambda i: expected[i], reverse=True)

    def dcg(order: Sequence[int]) -> float:
        return sum(
            (2 ** (max(0.0, min(100.0, expected[index])) / 100.0) - 1)
            / math.log2(position + 2)
            for position, index in enumerate(order[:k])
        )

    ideal = dcg(ideal_order)
    return dcg(predicted_order) / ideal if ideal else 1.0


def top_k_overlap(expected: Sequence[float], predicted: Sequence[float], k: int = 10) -> float | None:
    if len(expected) != len(predicted) or not expected:
        return None
    k = min(k, len(expected))
    expected_top = {i for i in sorted(range(len(expected)), key=lambda i: expected[i], reverse=True)[:k]}
    predicted_top = {i for i in sorted(range(len(predicted)), key=lambda i: predicted[i], reverse=True)[:k]}
    return len(expected_top & predicted_top) / k if k else None


def binary_metrics(expected: Iterable[bool], predicted: Iterable[bool]) -> Dict[str, Any]:
    pairs = list(zip(expected, predicted))
    tp = sum(a and b for a, b in pairs)
    tn = sum(not a and not b for a, b in pairs)
    fp = sum(not a and b for a, b in pairs)
    fn = sum(a and not b for a, b in pairs)

    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "support": len(pairs),
        "positive_support": tp + fn,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
    }


def multiclass_metrics(expected: Iterable[str], predicted: Iterable[str]) -> Dict[str, Any]:
    expected = [value.upper() for value in expected]
    predicted = [value.upper() for value in predicted]
    labels = list(RISK_LEVELS)
    confusion = {label: {other: 0 for other in labels} for label in labels}
    for actual, guess in zip(expected, predicted):
        if actual in confusion and guess in labels:
            confusion[actual][guess] += 1

    per_class: Dict[str, Any] = {}
    f1_values: List[float] = []
    all_f1_values: List[float] = []
    for label in labels:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        predicted_support = sum(confusion[other][label] for other in labels)
        fp = predicted_support - tp
        fn = support - tp
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / support if support else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else None
        )
        per_class[label] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        if support and f1 is not None:
            f1_values.append(f1)
            all_f1_values.append(f1)
        else:
            # Explicitly report zero for a declared class with no gold support.
            all_f1_values.append(0.0)

    total = len(expected)
    correct = sum(actual == guess for actual, guess in zip(expected, predicted))
    return {
        "support": total,
        "accuracy": correct / total if total else None,
        "macro_f1_observed_classes": _mean(f1_values),
        "macro_f1_all_declared_classes": _mean(all_f1_values),
        "classes_without_support": [label for label in labels if not per_class[label]["support"]],
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def evaluate_relevance(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    expected: List[float] = []
    predicted: List[float] = []
    invalid = 0
    for record in records:
        gold = record["gold"].get("relevance_score")
        guess = record["predictions"].get("relevance_score")
        if isinstance(gold, (int, float)) and isinstance(guess, (int, float)) and 0 <= guess <= 100:
            expected.append(float(gold))
            predicted.append(float(guess))
        else:
            invalid += 1
    return {
        "support": len(expected),
        "invalid_predictions": invalid,
        "spearman": spearman_correlation(expected, predicted),
        "ndcg_at_10": ndcg_at_k(expected, predicted, 10),
        "ndcg_at_10_definition": "graded_gain_2_power_normalized_score_0_1",
        "ndcg_at_10_legacy": ndcg_at_k_legacy(expected, predicted, 10),
        "top_10_overlap": top_k_overlap(expected, predicted, 10),
        "mean_absolute_error": _mean([abs(a - b) for a, b in zip(expected, predicted)]),
    }


def evaluate_risk(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    expected_breaking: List[bool] = []
    predicted_breaking: List[bool] = []
    expected_risk: List[str] = []
    predicted_risk: List[str] = []
    expected_category: List[str] = []
    predicted_category: List[str] = []
    invalid = 0
    for record in records:
        gold = record["gold"]
        guess = record["predictions"]
        risk = str(guess.get("risk_level", "")).upper()
        breaking = guess.get("breaking_changes")
        if risk not in RISK_LEVELS or not isinstance(breaking, bool):
            invalid += 1
            continue
        expected_breaking.append(bool(gold["breaking_changes"]))
        predicted_breaking.append(breaking)
        expected_risk.append(str(gold["risk_level"]).upper())
        predicted_risk.append(risk)
        if gold.get("risk_category") is not None and guess.get("risk_category") is not None:
            expected_category.append(str(gold["risk_category"]).upper())
            predicted_category.append(str(guess["risk_category"]).upper())
    category_correct = sum(a == b for a, b in zip(expected_category, predicted_category))
    return {
        "support": len(expected_risk),
        "invalid_predictions": invalid,
        "breaking_changes": binary_metrics(expected_breaking, predicted_breaking),
        "risk_level": multiclass_metrics(expected_risk, predicted_risk),
        "risk_category": {
            "support": len(expected_category),
            "accuracy": category_correct / len(expected_category) if expected_category else None,
        },
    }
