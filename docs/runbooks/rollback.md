# Rollback Runbook

## When to Roll Back

A bad deployment causes test or production failures not fixed by config change.

## Steps

1. Identify last good Git SHA.
2. Re-deploy that image to ECS.
3. Run `alembic downgrade` to the previous migration if the new migration is bad.
4. Verify `/health` returns 200 and DOD report is green.
5. If data corruption occurred, restore from RDS snapshot.

## Rollback Verification

- `terraform plan` shows no unexpected drift.
- `pytest tests/` passes.
- `make contracts` produces no diffs.
