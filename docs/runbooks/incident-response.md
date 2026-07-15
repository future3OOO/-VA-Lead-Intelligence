# Incident Response Runbook

## Scope

Unplanned degradation of the VA Lead Intelligence API, workers, or data pipeline.

## Severity Levels

- **SEV-1**: API unavailable, data loss, or compliance breach.
- **SEV-2**: Major feature degraded (scoring, exports, crawling).
- **SEV-3**: Minor impact, partial slowness, or single source failure.

## Response Steps

1. **Detect**: Alert from `/health` or Temporal UI.
2. **Triage**: Check `make handover` artifacts are current and CI status.
3. **Contain**: Disable failing source via `config/source-policy/default.yaml`.
4. **Mitigate**: Roll back to last known good image or migration.
5. **Communicate**: Notify on-call channel with incident ID and customer impact.
6. **Resolve**: Merge fix, re-run `make handover`, and verify in staging.

## Contacts

- On-call: see PagerDuty rotation.
- Engineering lead: `engineering@example.com`.
