#!/usr/bin/env python3
"""Run frozen benchmark fixtures and produce a report."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

BENCHMARK_DIR = REPO_ROOT / "benchmark"
SOURCE_ENGINE_BENCHMARK_DIR = REPO_ROOT / "quality" / "benchmarks" / "source-engine"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    from core.policy_engine import evaluate_jurisdiction
    from core.scorer import score

    features = fixture.get("features", {})
    outcome = score(features)
    jurisdiction = evaluate_jurisdiction(features.get("country_code", ""))
    allowed = jurisdiction["allowed"]
    actual_pass = outcome["passed"] and allowed
    expected_pass = fixture.get("expected_pass")
    return {
        "fixture_id": fixture["fixture_id"],
        "expected_pass": expected_pass,
        "actual_pass": actual_pass,
        "score": outcome["score"],
        "jurisdiction_allowed": allowed,
        "passed": actual_pass == expected_pass,
    }


def _is_blocked_source_hit(hit: dict[str, Any]) -> bool:
    """Determine whether a source hit is blocked by jurisdiction or fixture directive."""
    if hit.get("jurisdiction_action") == "block":
        return True
    location = hit.get("location_raw", "")
    if not location:
        return False
    from core.policy_engine import evaluate_jurisdiction

    # Accept location formats like "Sydney, AU" or "EU-DE".
    country_code = location.split("-")[-1].strip().upper()
    if not country_code:
        return False
    return not evaluate_jurisdiction(country_code)["allowed"]


def _content_hash(hit: dict[str, Any]) -> str:
    explicit = hit.get("content_hash", "")
    if explicit:
        return str(explicit)
    payload = {
        "title": str(hit.get("title", "")).strip().lower(),
        "body": str(hit.get("body_excerpt", "")).strip().lower(),
        "company": str(hit.get("company_name_raw", "")).strip().lower(),
        "domain": str(hit.get("company_domain_raw", "")).strip().lower(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def run_source_engine_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a source-engine benchmark fixture."""
    from config.enums import IntentLabel
    from services.source_engine.resolver import EXCLUDED_INTENTS
    from services.source_engine.scorer import score_source_hit

    hits = fixture.get("source_hits", [])
    expected = fixture.get("expected", {})
    seen_hashes: set[tuple[str | None, str]] = set()
    duplicates = 0
    allowed_hits: list[bool] = []
    qualified_hits: list[bool] = []

    for hit in hits:
        blocked = _is_blocked_source_hit(hit)
        allowed_hits.append(not blocked)
        score = score_source_hit(hit)
        intent = str(hit.get("intent_label", "")).strip()
        intent_label = IntentLabel(intent) if intent else IntentLabel.UNRESOLVED
        qualified = not blocked and intent_label.value not in EXCLUDED_INTENTS and score >= 0.5
        qualified_hits.append(qualified)

        content_hash = _content_hash(hit)
        key = (hit.get("source_key"), content_hash)
        if key in seen_hashes:
            duplicates += 1
        seen_hashes.add(key)

    actual_allowed = all(allowed_hits) if allowed_hits else False
    actual_qualified = any(qualified_hits) if qualified_hits else False

    passed = True
    if "allowed" in expected and actual_allowed != expected["allowed"]:
        passed = False
    if "qualified" in expected and actual_qualified != expected["qualified"]:
        passed = False
    if "duplicates" in expected and duplicates != expected["duplicates"]:
        passed = False

    return {
        "fixture_id": fixture.get("description", "unknown"),
        "expected": expected,
        "actual": {
            "allowed": actual_allowed,
            "qualified": actual_qualified,
            "duplicates": duplicates,
        },
        "passed": passed,
    }


def main() -> int:
    results: list[dict[str, Any]] = []
    failures = 0
    for path in sorted(BENCHMARK_DIR.glob("fixtures/*.yaml")):
        fixture = load_yaml(path)
        result = run_fixture(fixture)
        results.append(result)
        if not result["passed"]:
            failures += 1

    for path in sorted(SOURCE_ENGINE_BENCHMARK_DIR.glob("*.yaml")):
        fixture = load_yaml(path)
        result = run_source_engine_fixture(fixture)
        results.append(result)
        if not result["passed"]:
            failures += 1

    report = {
        "total": len(results),
        "failures": failures,
        "results": results,
    }

    report_path = BENCHMARK_DIR / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    guide_path = BENCHMARK_DIR / "label-guide.md"
    guide = """# Benchmark Label Guide

Each fixture under `benchmark/fixtures/` is a labeled scoring scenario for the
legacy `core.scorer`.

Each fixture under `quality/benchmarks/source-engine/` is a labeled source-engine
scenario using `services.source_engine.scorer`.

- `expected_pass`: the intended qualification outcome (legacy fixtures).
- `expected`: a map of `allowed`, `qualified`, and/or `duplicates` (source-engine fixtures).
- `features`: a normalized feature vector consumed by `core.scorer.score`.
- `source_hits`: raw source-engine hits consumed by `services.source_engine.scorer.score_source_hit`.

Final qualification is `score_passed and jurisdiction_allowed`.

To add a fixture:
1. Copy an existing file in `benchmark/fixtures/` or `quality/benchmarks/source-engine/`.
2. Update `fixture_id`/`description` and `expected`/`expected_pass`.
3. Provide a realistic feature vector or source hit.
4. Run `python scripts/build_benchmark.py` and commit `benchmark/report.json`.
"""
    guide_path.write_text(guide)

    print(f"Benchmark: {len(results)} fixtures, {failures} failures")
    if failures:
        print("Failing fixtures:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['fixture_id']}: {r}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
