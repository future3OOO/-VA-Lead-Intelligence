# Scoring Tuning Runbook

## Scope

Adjusting capability weights, thresholds, or signals.

## Steps

1. Edit `config/scorecards/default.yaml` or `config/capability-taxonomy/capabilities.yaml`.
2. Run `make config-validate`.
3. Run `make benchmark` and inspect `benchmark/report.json`.
4. If benchmark fails, revert or iterate until green.
5. Update `approved_by` and `approved_at` fields.
6. Commit and run `make handover` before deployment.

## Guardrails

- Scorecard changes are versioned and require a DOD review.
- Never modify the frozen benchmark fixtures to match a new scorecard.
