"""Lead scoring engine driven by YAML scorecards and feature vectors."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCORECARD = REPO_ROOT / "config" / "scorecards" / "default.yaml"


def load_scorecard(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_SCORECARD
    return yaml.safe_load(p.read_text()) or {}


def evaluate_signal(value: Any, rule: dict[str, Any]) -> float:
    op = rule.get("operator", "exists")
    target = rule.get("value")
    targets = rule.get("values", [])
    weight = float(rule.get("weight", 1.0))

    if op == "exists":
        return weight if value is not None else 0.0
    if op == "equals":
        return weight if value == target else 0.0
    if op == "in":
        return weight if value in targets else 0.0
    if op == "not_in":
        return weight if value not in targets else 0.0
    if op == "gte" and isinstance(value, (int, float)):
        return weight if value >= float(target or 0) else 0.0
    if op == "lte" and isinstance(value, (int, float)):
        return weight if value <= float(target or float("inf")) else 0.0
    if op == "contains_any" and isinstance(value, (list, str)):
        haystack = value if isinstance(value, list) else value.split(",")
        haystack = [str(item).strip().lower() for item in haystack]
        return weight if any(str(t).lower() in haystack for t in targets) else 0.0
    return 0.0


def score(features: dict[str, Any], scorecard: dict[str, Any] | None = None) -> dict[str, Any]:
    card = scorecard or load_scorecard()
    dimensions = card.get("dimensions", [])
    min_score = float(card.get("min_score", 0))
    dimension_scores: dict[str, float] = {}
    explanations: list[str] = []
    total = 0.0

    for dimension in dimensions:
        dim_score = 0.0
        for signal in dimension.get("signals", []):
            name = signal["name"]
            value = features.get(name)
            signal_score = evaluate_signal(value, signal)
            dim_score += signal_score
            if signal_score:
                explanations.append(f"{dimension['id']}/{name}: matched ({signal_score})")
        dimension_scores[dimension["id"]] = dim_score
        total += dim_score * float(dimension.get("weight", 0))

    score_value = round(total * 100, 2)
    passed = score_value >= min_score
    return {
        "score": score_value,
        "min_score": min_score,
        "passed": passed,
        "dimension_scores": {k: round(v * 100, 2) for k, v in dimension_scores.items()},
        "explanations": explanations,
    }
