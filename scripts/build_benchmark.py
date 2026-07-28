#!/usr/bin/env python3
"""Run frozen benchmark fixtures and produce a report."""

from __future__ import annotations

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


def run_source_engine_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a source-engine benchmark fixture using production runtime logic.

    Reuses SourceRunner._process_hit for classification/scoring and
    SourceRunner._is_qualified, and applies the same jurisdiction gate the
    runner uses in production. Deduplication is driven by the computed
    content_hash.
    """
    from services.source_engine.runner import SourceRunner, _jurisdiction_allowed

    runner = SourceRunner()
    hits = fixture.get("source_hits", [])
    expected = fixture.get("expected", {})
    seen_hashes: set[tuple[str | None, str]] = set()
    duplicates = 0
    allowed_hits: list[bool] = []
    qualified_hits: list[bool] = []

    for raw in hits:
        hit = runner._process_hit(raw)
        content_hash = hit.get("content_hash", "")
        key = (hit.get("source_key"), content_hash)
        if key in seen_hashes:
            duplicates += 1
            continue
        seen_hashes.add(key)

        allowed = _jurisdiction_allowed(hit.get("location_raw"))
        allowed_hits.append(allowed)
        qualified = allowed and runner._is_qualified(hit, 0.5)
        qualified_hits.append(qualified)

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
