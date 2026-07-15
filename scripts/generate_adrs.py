#!/usr/bin/env python3
"""Generate ADR markdown files from a structured list."""
from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ADRS = [
    {
        "id": "ADR-001",
        "title": "Repository boundaries and system scope",
        "status": "accepted",
        "context": "The VA Lead-Generation Module must ingest public signals, score companies, and export qualified leads while remaining a bounded context that other products can integrate via events and REST.",
        "decision": "Build `va-lead-intelligence` as a stateful Python service with a public FastAPI, async workers, and a JSON/PostgreSQL event store. Scope excludes CRM/ERP outbound execution and email delivery.",
        "consequences": "Teams outside the module can consume `lead-qualified` events without direct database access. We own the scoring and sourcing policies end-to-end.",
    },
    {
        "id": "ADR-002",
        "title": "Domain specification as source of truth",
        "status": "accepted",
        "context": "Pydantic, SQLAlchemy, and OpenAPI schemas drifted in earlier prototypes because they were edited independently.",
        "decision": "`spec/domain.yaml` is the single source of truth. `scripts/generate_models.py` emits Pydantic models, SQLAlchemy models, FastAPI routers, and event classes.",
        "consequences": "All downstream artifacts are regenerated from one file. Schema changes require a spec edit followed by `make contracts` and `make migration-check`.",
    },
    {
        "id": "ADR-003",
        "title": "Persistence layer",
        "status": "accepted",
        "context": "The system stores normalized companies, signals, campaigns, and audit events with strong consistency per workspace.",
        "decision": "Use PostgreSQL 15+ with SQLAlchemy 2.0, asyncpg for application traffic, and Alembic for schema migrations. JSONB columns carry extensible metadata.",
        "consequences": "Full ACID per workspace, portable SQL, and mature migration tooling. We accept the operational complexity of a relational database over a document store.",
    },
    {
        "id": "ADR-004",
        "title": "API and event serialization",
        "status": "accepted",
        "context": "Contracts must be machine-readable for frontend, downstream consumers, and compliance review.",
        "decision": "Use FastAPI 0.111+ and Pydantic v2. Event schemas and API DTOs share the same generated Pydantic classes, then are exported to JSON Schema and OpenAPI.",
        "consequences": "Validation and serialization logic live in one place. OpenAPI and JSON Schema are always aligned with runtime code.",
    },
    {
        "id": "ADR-005",
        "title": "Durable workflow execution",
        "status": "accepted",
        "context": "Campaign runs, classifier pipelines, and export jobs can be long-lived and must survive process restarts.",
        "decision": "Use Temporal for durable workflows and activities. Redis supports task queues and rate-limit counters. Temporal provides visibility, retries, and sagas.",
        "consequences": "Workflow definitions are explicit and versioned. We add infrastructure but avoid ad-hoc cron and fragile retry loops.",
    },
    {
        "id": "ADR-006",
        "title": "Crawling runtime",
        "status": "accepted",
        "context": "Python crawling libraries are either sync and slow or require heavy custom code to handle proxies, queues, and deduplication.",
        "decision": "Use Crawlee (Node/TypeScript) under `services/crawler/`, triggered via Temporal activities and writing normalized source events to the main API.",
        "consequences": "A second runtime is introduced. The boundary between crawler and core is HTTP over internal mTLS, keeping state and scoring in Python.",
    },
    {
        "id": "ADR-007",
        "title": "Scoring and taxonomy as configuration",
        "status": "accepted",
        "context": "Sales and product teams need to tune lead qualification without deploying code.",
        "decision": "Capability taxonomy and scorecards are YAML under `config/capability-taxonomy/` and `config/scorecards/`. The scorer loads them at startup and validates with JSON Schema.",
        "consequences": "Scorecard changes are versioned, auditable, and testable against the frozen benchmark before production.",
    },
    {
        "id": "ADR-008",
        "title": "Source and jurisdiction policy engine",
        "status": "accepted",
        "context": "Crawling and scoring must respect robots.txt, rate limits, privacy law, and customer-specific source restrictions.",
        "decision": "Encode source policies and jurisdiction rules as YAML. A `PolicyEngine` class resolves allow/block/permitted-source lists per workspace at runtime.",
        "consequences": "Compliance logic is explicit and reviewable. New regulations or source bans are config changes, not code changes.",
    },
    {
        "id": "ADR-009",
        "title": "Multi-tenant authorization",
        "status": "accepted",
        "context": "Multiple customer workspaces share one deployment, and tenants must not read each other's data.",
        "decision": "Use `x-workspace-id` and `x-api-key` headers. The `require_workspace` dependency validates the API key and returns the workspace UUID. All queries filter by `workspace_id`.",
        "consequences": "Row-level tenant isolation is enforced by query filters, not RLS, because asyncpg + SQLAlchemy RLS `SET` statements are complex. This is documented as a deliberate trade-off and tested.",
    },
    {
        "id": "ADR-010",
        "title": "Audit and event sourcing",
        "status": "accepted",
        "context": "Regulators and customers require an immutable record of decisions, exports, and score changes.",
        "decision": "Append immutable `audit_event` records for every mutation. Domain events carry `event_id`, `correlation_id`, `workspace_id`, and `occurred_at`.",
        "consequences": "Audit events are insert-only. Deletion is implemented as a `deleted` status with an audit record, never `DELETE`.",
    },
    {
        "id": "ADR-011",
        "title": "Observability and runbooks",
        "status": "accepted",
        "context": "Production incidents must be diagnosable without SSHing into workers.",
        "decision": "Emit structured JSON logs, expose FastAPI `/health` and `/metrics`, and write operational runbooks in `docs/runbooks/`. Temporal UI provides workflow visibility.",
        "consequences": "On-call can follow runbooks. Health endpoints are wired into load balancer and Terraform health checks.",
    },
    {
        "id": "ADR-012",
        "title": "Handover and release gates",
        "status": "accepted",
        "context": "Release artifacts drift from code unless generation is enforced in CI.",
        "decision": "`make handover` regenerates OpenAPI, JSON Schema, ERD, migration plan, benchmark report, and DOD traceability, then fails on uncommitted changes or missing ADR approvals.",
        "consequences": "A green `handover` target guarantees the committed package matches the runtime. CI blocks merges when artifacts are stale.",
    },
]


def render(adr: dict[str, Any]) -> str:
    return f"""# {adr['id']} — {adr['title']}

**Status:** {adr['status']}<br />
**Date:** 2026-07-15

## Context

{adr['context']}

## Decision

{adr['decision']}

## Consequences

{adr['consequences']}

## Related

- `docs/adr/`
- `spec/domain.yaml`
- `Makefile`
"""


def main() -> int:
    out_dir = REPO_ROOT / "docs" / "adr"
    out_dir.mkdir(parents=True, exist_ok=True)
    for adr in ADRS:
        (out_dir / f"{adr['id']}.md").write_text(render(adr))
    print(f"Generated {len(ADRS)} ADRs in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
