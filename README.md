# VA Lead Intelligence

Production-ready lead-generation platform for virtual assistants, built on FastAPI, SQLAlchemy, Pydantic, Temporal, and Terraform.

## What this does (in plain English)

This platform finds **real Australian and New Zealand businesses** that are likely to need remote virtual-assistant (VA) support, scores them, and exports a ranked list with contact details and a short explanation of *why* each one is a good prospect.

### Where the leads come from

The main live source is **OpenStreetMap** — a free, public business directory. Every business listed there has a real name, address, phone number, email, and/or website. We query OpenStreetMap for business types that naturally create admin work, for example:

- Real-estate agencies and property managers
- Accountants, bookkeepers, tax agents, and financial planners
- Insurance and mortgage brokers
- Law firms and conveyancers
- Builders, electricians, plumbers, painters, roofers, and other trade businesses
- Construction companies and home-service providers

We do **not** scrape LinkedIn, Google, or private business directories, and we do **not** use fake data.

### How we decide a company needs a VA

Each business type is mapped to the kind of remote admin work that business usually needs:

| Business type | Typical VA work |
|---------------|-----------------|
| Real estate / property management | Listing admin, CRM updates, buyer/tenant follow-up, appointment scheduling, rent-roll data entry |
| Accounting / bookkeeping / tax | Client file admin, data entry, invoicing, reconciliations, inbox/CRM management, compliance paperwork |
| Insurance / mortgage broking | Claims/loan file processing, scheduling, customer enquiries, CRM updates, documentation |
| Legal / conveyancing | Client intake, document prep, diary management, billing admin, filing |
| Trades / construction / home services | Job scheduling, dispatch, invoicing, customer follow-up, maintenance coordination |

Every lead gets a **score out of 100** and a rank:

- **High (75+)** — strong VA fit: the business type creates a clear admin burden, the role can be done remotely, and we have a contact route.
- **Medium (55–74)** — good sector but the available signal is weaker (for example, a job-board post for a non-VA role at a target firm).
- **Low (<55)** — weaker fit or a senior professional role that the firm is hiring for directly.

Senior professional job posts (for example "Senior Accountant" or "Lead Lawyer") are **excluded** from the top results because those are not VA roles, even if the firm itself may still need admin help.

### What you get

The export is a CSV with one row per lead:

- `company_name` and `primary_domain`
- `job_title` — the VA-suitable role we matched to that business type
- `location` — city/suburb or lat/lon in Australia / New Zealand
- `workplace_type` — `hybrid` or `remote` (on-site-only posts are filtered out)
- `category` — Property/Facilities, Financial Services, Legal/Professional, Home Services/Construction, etc.
- `qualification_score` and `rank` — 0–100 score and High/Medium/Low
- `explanation` — a short, human-readable reason why this lead scored well
- `best_email`, `best_phone`, `best_form` — best available contact route
- `source_url` — link back to the OpenStreetMap page or the job posting

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

## Generating your first ANZ lead list

Once the local database is running (`docker compose up -d`), you can produce a ranked CSV of ANZ leads:

```bash
python scripts/run_source_engine.py \
  --workspace-id 985cfd3b-a3af-4217-8b10-8c46b0915b92 \
  --campaign-id 2ddbdd5f-3e7e-4667-a3ca-4ee2dfb3bdfc \
  --source-keys openstreetmap

python scripts/export_leads_csv.py \
  --workspace-id 985cfd3b-a3af-4217-8b10-8c46b0915b92 \
  --region anz \
  --leads-path /tmp/anz_remote_leads_with_contacts.csv \
  --companies-path /tmp/anz_all_companies.csv
```

The first command fetches the latest OpenStreetMap business listings. The second command scores them and writes the two CSV files. Change `--leads-path` and `--companies-path` to wherever you want the files saved.

### Optional: add named contacts

If you want named hiring managers (e.g. "John Smith, Office Manager") instead of generic inboxes, you can run the bounded `team_pages` enrichment. It reads the domains already found by OpenStreetMap, visits the `/team` and `/about` pages those companies publish themselves, and extracts real people, titles, emails, and LinkedIn profiles. It checks `robots.txt` and only looks at the pages the site makes public.

```bash
python scripts/extract_team_pages.py \
  --workspace-id 985cfd3b-a3af-4217-8b10-8c46b0915b92 \
  --campaign-id 2ddbdd5f-3e7e-4667-a3ca-4ee2dfb3bdfc \
  --max-domains 100
```

Then run `export_leads_csv.py` again and the `named_contact_*` columns will be filled where available.

## Handover

`make handover` is the production-readiness gate. It fails if generated artifacts drift, tests fail, Terraform is invalid, or any DOD item lacks evidence.
