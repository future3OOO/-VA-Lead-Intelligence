# Source Shutdown Runbook

## 1. Immediate stop

Set the environment variable or application setting for the source kill switch:

```bash
export SOURCES_GREENHOUSE_ENABLED=false
export SOURCES_LEVER_ENABLED=false
export SOURCES_ASHBY_ENABLED=false
export SOURCES_SMARTRECRUITERS_ENABLED=false
export SOURCES_COMPANY_WEB_ENABLED=false
export SOURCES_SEARCH_DISCOVERY_ENABLED=false
export SOURCES_HUNTER_ENABLED=false
```

Restart the API worker or Temporal worker to pick up the change.

## 2. Drain in-flight runs

List active `source_run` records:

```sql
SELECT id, source_key, status, started_at
FROM source_run
WHERE status IN ('pending', 'running');
```

Wait for `status` to become `succeeded`, `failed` or `cancelled` before deploying schema changes.

## 3. Disable a single source

Edit `config/sources/source-registry.yaml` and set `status: disabled` for the source, then run:

```bash
make config-validate
```

## 4. Rollback a migration

```bash
alembic downgrade -1
```

## 5. Data retention

Purge stale source hits for a source:

```python
from services.source_engine.config import SourceRegistryLoader
from services.source_engine.retention import RetentionPolicy

cfg = SourceRegistryLoader().get("greenhouse_jobs")
policy = RetentionPolicy(cfg)
# await policy.apply_to_workspace(session, workspace_id)
```

## 6. Post-incident review

Capture the source key, time window, error counts and affected workspace IDs in the incident log.
