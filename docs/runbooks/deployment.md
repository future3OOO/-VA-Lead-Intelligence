# Deployment Runbook

## Pre-deployment

1. Ensure branch is green on CI (`make handover` passes).
2. Review `docs/adr/` for any `proposed` ADRs.
3. Confirm `config/` policies are approved and not expired.

## Deployment

1. Merge PR to `main`.
2. Tag release: `git tag -a v$(cat version.txt)`.
3. Build and push container image.
4. Run `terraform plan` and `terraform apply` for the target environment.
5. Run `alembic upgrade head`.
6. Verify endpoints and Temporal workflows.

## Post-deployment

1. Watch error rate and latency for 30 minutes.
2. Run a smoke test campaign.
3. Close deployment ticket.
