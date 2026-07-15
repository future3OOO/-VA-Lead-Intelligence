# Benchmark Label Guide

Each fixture under `benchmark/fixtures/` is a labeled scoring scenario.

- `expected_pass`: the intended qualification outcome.
- `features`: a normalized feature vector consumed by `core.scorer.score`.

Final qualification is `score_passed and jurisdiction_allowed`.

To add a fixture:
1. Copy an existing file in `benchmark/fixtures/`.
2. Update `fixture_id` and `expected_pass`.
3. Provide a realistic feature vector.
4. Run `python scripts/build_benchmark.py` and commit `benchmark/report.json`.
