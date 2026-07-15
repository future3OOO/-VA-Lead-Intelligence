# VA Lead Intelligence

Production-ready lead-generation platform for virtual assistants, built on FastAPI, SQLAlchemy, Pydantic, Temporal, and Terraform.

## Quick start

```bash
make install
make test
make handover
```

For local infrastructure:

```bash
docker compose up -d
make migration-check
```

## Makefile targets

- `make lint` — ruff lint and format check
- `make typecheck` — mypy strict
- `make test` — pytest suite
- `make contracts` — export OpenAPI and JSON Schemas
- `make config-validate` — validate taxonomy/scorecard/policy YAML
- `make migration-check` — Alembic upgrade and ERD render
- `make benchmark` — frozen benchmark and report
- `make infra-check` — Terraform fmt/validate
- `make dod-report` — requirement-to-test traceability
- `make handover` — regenerate, validate, and bundle all release artifacts

## Architecture

- `spec/domain.yaml` is the single source of truth for domain models, events, and API contracts.
- `scripts/generate_models.py` regenerates Pydantic models, SQLAlchemy models, events, and FastAPI routers from `spec/domain.yaml`.
- `config/scorecards/default.yaml` and `config/source-policy/default.yaml` drive runtime scoring and compliance.
- `infra/terraform/` contains AWS ECS/RDS/Redis/ElastiCache modules and the environment catalogue.
- `docs/adr/` contains accepted Architecture Decision Records.
- `docs/runbooks/` contains operational playbooks.

## Handover

`make handover` is the production-readiness gate. It fails if generated artifacts drift, tests fail, Terraform is invalid, or any DOD item lacks evidence.
