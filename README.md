# VA Lead Intelligence

Production-ready lead-generation platform for virtual assistants, built on FastAPI, SQLAlchemy, Pydantic, Temporal, and Terraform.

## What this does

The engine finds small and midsize businesses in Australia and New Zealand that are likely to need virtual-assistant support. It pulls from public, bounded sources, normalizes the data, scores each lead, resolves companies, enriches contact routes, and exports a ranked CSV.

Primary sources:

- `openstreetmap` — public Overpass API for real ANZ business listings (real estate, property management, accounting, legal, insurance/financial advisory, bookkeeping, construction, trades).
- `finance_directory` — public Australian finance-professionals directory (`financedirectory.net.au`).
- `nz_finance_advisers` — public New Zealand FSPR adviser directory (`financeadvisers.co.nz`).
- `team_pages` — bounded crawl of `/team`, `/about`, `/people`, `/leadership`, `/directors`, `/contact`, etc., to extract named contacts, emails, phones, and LinkedIn profiles.
- `company_web` — bounded breadth-first website crawl for contact routes.
- `manual_seed` — CSV/JSON seed import.

Each source is configured in `config/sources/source-registry.yaml` with rate limits, kill switches, and retention policies. All web crawlers respect `robots.txt`.

## Quick start

### 1. Install and start the database

```bash
# Copy default environment variables
cp .env.example .env

# Create the Python virtual environment and install dependencies
make install

# Start Postgres, Redis, and Temporal
docker compose up -d

# Run Alembic migrations and render the ERD
make migration-check
```

The default `.env` connects to:

- Postgres: `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres`
- Redis: `redis://localhost:6379/0`
- Temporal: `localhost:7233`
- API key: `dev-api-key`

### 2. Run the test suite

```bash
make test
make lint
make typecheck
```

### 3. Start the API (optional)

```bash
.venv/bin/python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Or use the Docker Compose `api` service:

```bash
docker compose up -d api
```

The OpenAPI docs are at `http://localhost:8000/docs`.

## Running the source engine

### Create a workspace and campaign

If the API is running, use the endpoints:

```bash
export API_KEY=dev-api-key

# Create a workspace
curl -X POST http://localhost:8000/workspaces \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -H "x-workspace-id: 00000000-0000-0000-0000-000000000000" \
  -d '{
    "name": "VA Lead Intelligence",
    "slug": "va-leads",
    "billing_email": "ops@example.com",
    "plan": "trial"
  }'

# Create a campaign in that workspace
curl -X POST http://localhost:8000/campaigns \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -H "x-workspace-id: <workspace-uuid>" \
  -d '{
    "name": "ANZ VA leads",
    "score_threshold": 0.5,
    "status": "active"
  }'
```

Keep the returned `workspace_id` and `campaign_id` for the run scripts.

### Run sources from the command line

```bash
WORKSPACE_ID="<workspace-uuid>"
CAMPAIGN_ID="<campaign-uuid>"

# Run the full enabled portfolio
.venv/bin/python scripts/run_source_engine.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID"

# Run one source only
.venv/bin/python scripts/run_source_engine.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --source-keys openstreetmap

# Override adapter config (example: limit NZ finance pages for a quick test)
.venv/bin/python scripts/run_source_engine.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --source-keys nz_finance_advisers \
  --query-overrides '{"nz_finance_advisers": {"max_list_pages": 5}}'
```

Source keys available:

- `openstreetmap`
- `finance_directory`
- `nz_finance_advisers`
- `team_pages`
- `company_web`
- `manual_seed`

### Backfill named contacts from company websites

After the main sources have run, enrich any companies that still lack a named contact:

```bash
.venv/bin/python scripts/extract_team_pages_missing.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --max-domains 1000
```

You can also run the older `extract_team_pages.py` against the domains with the most source hits:

```bash
.venv/bin/python scripts/extract_team_pages.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --max-domains 1000
```

### Export leads and companies

```bash
.venv/bin/python scripts/export_leads_csv.py \
  --workspace-id "$WORKSPACE_ID" \
  --region anz \
  --min-rank medium \
  --leads-path exports/anz_remote_leads_with_contacts.csv \
  --companies-path exports/anz_all_companies.csv
```

Columns in `anz_remote_leads_with_contacts.csv`:

- `company_name` / `primary_domain`
- `job_title` — synthetic VA-relevant title for OSM listings, or real job title for job-board hits
- `location`, `workplace_type`
- `category` — Property/Facilities, Financial Services, Home Services/Construction, Real Estate, etc.
- `source` / `source_url`
- `intent_label`
- `published_at`
- `qualification_score` / `rank` — High, Medium, Low
- `explanation` — human-readable reason this is a VA lead
- `best_email` / `best_phone` / `best_form`
- `named_contact_name` / `named_contact_title` / `named_contact_email` / `named_contact_linkedin`

### Check named-contact coverage

```bash
# Companies with a named contact
psql -U postgres -d postgres -c \
  "SELECT COUNT(DISTINCT c.id) FILTER (WHERE cr.route_type = 'named_contact') AS named, COUNT(DISTINCT c.id) AS total FROM company c LEFT JOIN contact_route cr ON cr.company_id = c.id WHERE c.workspace_id = '$WORKSPACE_ID';"
```

## Pipeline overview

```
Source Registry / Query Library
        |
        v
SourceRunner -> BaseSourceAdapter.fetch()
        |
        v
normalize() -> SourceHit
        |
        v
classify_intent() -> IntentLabel
score_source_hit() -> priority
        |
        v
resolve_company() -> Company
        |
        v
enrich_contact_routes() -> ContactRoute(s)
        |
        v
persist DBSourceHit + DBSourceRun
        |
        v
export_leads_csv.py -> ranked CSV
```

More detail is in `docs/architecture/source-engine-data-flow.md` and `docs/architecture/source-access-matrix.md`.

## Source access matrix

| Source | Access Mode | Data Collected | Rate Limit | API Key | Kill Switch |
|--------|-------------|----------------|------------|---------|-------------|
| `manual_seed` | manual_import | company_name, title, body, contact_routes | none | none | `sources.manual.enabled` |
| `openstreetmap` | public_api | real ANZ business name, address, phone, email, website, operator, business category | 0.2 req/s | none | `sources.openstreetmap.enabled` |
| `finance_directory` | scoped_public_web_crawl | Australian finance-professional profile pages: company, website, phone, named principal | 2 req/s | none | `sources.finance_directory.enabled` |
| `nz_finance_advisers` | scoped_public_web_crawl | NZ FSPR adviser profiles and provider pages: adviser name, FAP, website, phone | 1 req/s | none | `sources.nz_finance_advisers.enabled` |
| `team_pages` | scoped_public_web_crawl | named contacts, job titles, emails, phones, LinkedIn profiles from `/team` and `/about` pages | 2 req/s | none | `sources.team_pages.enabled` |
| `company_web` | scoped_public_web_crawl | website contact routes and named people from priority pages | 2 req/s | none | `sources.company_web.enabled` |

See `docs/architecture/source-access-matrix.md` for prohibited access modes.

## Operational controls

- **Rate limiting**: token-bucket `RateLimiter` per adapter.
- **Concurrency**: `max_concurrency_per_host` caps parallel requests.
- **Kill switch**: source registry `kill_switch` disables an adapter at runtime.
- **Checkpoint**: `CheckpointStore` records last observed time per adapter/workspace.
- **Metrics**: `SourceMetrics` captures hit, duplicate, qualified and error counts.

## Makefile targets

- `make lint` — ruff lint and format check
- `make format` — auto-format source files
- `make typecheck` — mypy strict
- `make test` — pytest suite
- `make contracts` — export OpenAPI and JSON Schemas
- `make config-validate` — validate taxonomy/scorecard/policy YAML
- `make migration-check` — Alembic upgrade and ERD render
- `make benchmark` — frozen benchmark and report
- `make infra-check` — Terraform fmt/validate
- `make handover` — regenerate, validate and bundle all release artifacts

## Production-readiness

`make handover` is the production-readiness gate. It fails if generated artifacts drift, tests fail, Terraform is invalid, or any DOD item lacks evidence.

Run `make handover` before every PR.
