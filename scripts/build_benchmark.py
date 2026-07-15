#!/usr/bin/env python3
"""Run frozen benchmark fixtures and produce a report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = REPO_ROOT / "benchmark"


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


def main() -> int:
    results: list[dict[str, Any]] = []
    failures = 0
    for path in sorted(BENCHMARK_DIR.glob("fixtures/*.yaml")):
        fixture = load_yaml(path)
        result = run_fixture(fixture)
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

Each fixture under `benchmark/fixtures/` is a labeled scoring scenario.

- `expected_pass`: the intended qualification outcome.
- `features`: a normalized feature vector consumed by `core.scorer.score`.

Final qualification is `score_passed and jurisdiction_allowed`.

To add a fixture:
1. Copy an existing file in `benchmark/fixtures/`.
2. Update `fixture_id` and `expected_pass`.
3. Provide a realistic feature vector.
4. Run `python scripts/build_benchmark.py` and commit `benchmark/report.json`.
"""
    guide_path.write_text(guide)

    print(f"Benchmark: {len(results)} fixtures, {failures} failures")
    if failures:
        print("Failing fixtures:")
        for r in results:
            if not r["passed"]:
                print(
                    f"  - {r['fixture_id']}: expected {r['expected_pass']}, got {r['actual_pass']} (score {r['score']}, jurisdiction {r['jurisdiction_allowed']})"
                )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
