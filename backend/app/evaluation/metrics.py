"""不依赖第三方 ML 框架的评测指标实现。"""

from __future__ import annotations

from collections import Counter
from typing import Iterable


def accuracy(expected: list[str], predicted: list[str]) -> float:
    if not expected:
        return 0.0
    return sum(actual == guess for actual, guess in zip(expected, predicted)) / len(expected)


def macro_f1(expected: list[str], predicted: list[str], labels: Iterable[str]) -> float:
    scores: list[float] = []
    for label in labels:
        tp = sum(actual == label and guess == label for actual, guess in zip(expected, predicted))
        fp = sum(actual != label and guess == label for actual, guess in zip(expected, predicted))
        fn = sum(actual == label and guess != label for actual, guess in zip(expected, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def entity_prf(expected: list[set[tuple[str, str]]], predicted: list[set[tuple[str, str]]]) -> dict[str, float]:
    true_positive = sum(len(actual & guess) for actual, guess in zip(expected, predicted))
    false_positive = sum(len(guess - actual) for actual, guess in zip(expected, predicted))
    false_negative = sum(len(actual - guess) for actual, guess in zip(expected, predicted))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def confusion_matrix(expected: list[str], predicted: list[str], labels: list[str]) -> dict[str, dict[str, int]]:
    matrix = {row: {column: 0 for column in labels} for row in labels}
    for actual, guess in zip(expected, predicted):
        matrix.setdefault(actual, {column: 0 for column in labels})
        matrix[actual].setdefault(guess, 0)
        matrix[actual][guess] += 1
    return matrix


def per_intent_accuracy(expected: list[str], predicted: list[str]) -> dict[str, float]:
    totals: Counter[str] = Counter(expected)
    correct: Counter[str] = Counter(
        actual for actual, guess in zip(expected, predicted) if actual == guess
    )
    return {label: round(correct[label] / count, 6) for label, count in sorted(totals.items())}
