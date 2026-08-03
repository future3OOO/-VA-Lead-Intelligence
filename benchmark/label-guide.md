# Benchmark Label Guide

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
