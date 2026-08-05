# VA Lead Intelligence

VA Lead Intelligence builds a ranked list of Australian and New Zealand
businesses that may benefit from remote administrative support. It collects
business listings, finds contact details on official company websites, scores
the results, and exports readable CSV files plus a four-sheet Excel workbook.

This is a targeted prospecting tool. It is **not** a complete directory of every
business in Australia or New Zealand, and a lead does not mean that the company
is actively hiring.

## Current coverage

The checked-in configuration searches the country-level OpenStreetMap areas
`Australia` and `New Zealand`, plus two bounded finance directories. It targets
these sectors:

| Sector | Examples currently included |
|---|---|
| Property and real estate | Estate agencies and property managers |
| Financial services | Accountants, bookkeepers, insurance offices, financial advisers, and Australian/NZ finance-directory profiles |
| Legal services | Lawyers and legal practices |
| Trades and construction | Construction companies, plumbers, electricians, carpenters, painters, roofers, and HVAC businesses |
| Business support | Businesses tagged as administrative offices |

Coverage is limited by the data published by each source:

- OpenStreetMap queries the configured business **nodes** in Australia and New
  Zealand. Missing or differently tagged businesses will not appear.
- `finance_directory` processes at most 1,200 Australian profile pages per run.
- `nz_finance_advisers` processes at most 30 New Zealand list pages per run.
- Official-site enrichment only visits domains found during the source run and
  only keeps contact details that can be validated and associated safely.
- Each website crawl has a 30-second domain budget.

Therefore, “full scrape” in this guide means a **full run of the current
configuration**, not exhaustive ANZ market coverage.

## How OpenStreetMap discovery works

`openstreetmap` queries real business nodes through the public Overpass API. It
tries these endpoints in order and falls back when the first is unavailable or
rate-limited:

1. `https://z.overpass-api.de/api/interpreter`
2. `https://lz4.overpass-api.de/api/interpreter`
3. `https://maps.mail.ru/osm/tools/overpass/api/interpreter`

The complete checked-in business mapping is:

| OSM key | OSM value | Synthetic workload title | VA-fit category |
|---|---|---|---|
| `office` | `estate_agent` | Property Manager / Real Estate Office | real estate agency providing property management and property services |
| `office` | `property_manager` | Property Manager / Real Estate Office | real estate agency providing property management and property services |
| `office` | `real_estate` | Property Manager / Real Estate Office | real estate agency providing property management and property services |
| `office` | `accountant` | Accountant / Accounting Practice | accounting and tax services practice |
| `office` | `lawyer` | Lawyer / Legal Practice | law firm and legal services practice |
| `office` | `insurance` | Insurance Broker / Insurance Office | insurance brokerage and financial services |
| `office` | `financial_advisor` | Financial Planner / Financial Advisory | financial planning and advisory practice |
| `office` | `bookkeeper` | Bookkeeper / Bookkeeping Practice | bookkeeping and accounting support practice |
| `office` | `construction_company` | Operations Coordinator / Construction Office | construction and home services business |
| `office` | `administrative` | Administrative Assistant / Office | administrative and business support services |
| `craft` | `plumber` | Maintenance Coordinator / Plumbing Services | plumbing and home services trade |
| `craft` | `electrician` | Maintenance Coordinator / Electrical Services | electrical contractor and home services trade |
| `craft` | `carpenter` | Maintenance Coordinator / Carpentry Services | carpentry and home services trade |
| `craft` | `painter` | Maintenance Coordinator / Painting Services | painting and home services trade |
| `craft` | `roofer` | Maintenance Coordinator / Roofing Services | roofing and home services trade |
| `craft` | `hvac` | Maintenance Coordinator / HVAC Services | hvac and home services trade |

Each listing contributes its name, website, email, phone, address tags, brand,
and geographic coordinates. A `branch` or `addr:suburb` value is appended to
the company name when present so distinct offices are not collapsed. The
`operator` tag is retained as listing context only; it is never treated as a
person. Latitude/longitude is used when no address is available.

The synthetic title describes the likely administrative workload for that
sector. It is not an observed vacancy. OSM email and phone tags become contact
routes; a website remains company metadata and is not mislabeled as a contact
form. Requests run at the registry limit of 0.2 requests/second, use node-only
queries, and retry both endpoints with bounded per-request and overall query
deadlines after transient timeout or rate-limit failures.

## What the pipeline produces

The normal run has four steps:

1. **Discover companies** from OpenStreetMap and the two finance directories.
2. **Enrich contacts** from official company websites using three parallel
   shards.
3. **Export** ranked leads, one primary-contact row per lead, one row per
   validated person discovered in company or source-hit routes, and companies.
4. **Build the workbook** from those four canonical CSV exports.

The final files are written under `exports/`:

| File | Contents |
|---|---|
| `anz_remote_leads_with_contacts.csv` | One row per ranked lead with snapshot lead, company, and primary-contact IDs plus selected-person and generic-company fields |
| `anz_remote_leads_with_targeted_contacts.csv` | Byte-identical alias of the complete lead export |
| `anz_primary_contacts.csv` | Exactly one row per lead; selected person details or `primary_contact_status=unavailable` |
| `anz_contacts.csv` | One row per validated person discovered in company or source-hit routes, with every associated email, phone, and LinkedIn URL |
| `anz_all_companies.csv` | One row per company with the best collected routes |
| `anz_all_companies_targeted.csv` | Byte-identical alias of the company export |
| `anz_full_leads_with_targeted_contacts.xlsx` | Four-sheet prospecting workbook; Leads has one readable row per lead/contact association |

Everything under `exports/` is a generated local artifact. CSV and XLSX output
files are intentionally ignored by Git and must not be committed or pushed.

Person fields are kept separate from generic office details:

- join Leads to Primary Contacts on `lead_id`
- join Leads or Primary Contacts to Contacts where
  `primary_contact_id = contact_id`
- join any nonblank `company_id` to Companies; a lead that could not be
  resolved to a company is preserved with blank company/contact references
- `lead_id` is the winning source-hit ID for the current database/export state;
  use it for joins within a run, not as a permanent ID across clean re-scrapes
- `primary_contact_name`, `primary_contact_title`, `primary_contact_email`,
  `primary_contact_phone`, `primary_contact_linkedin`
- `company_email`, `company_phone`, `company_form`
- `best_email`, `best_phone`, `best_form` use a named route first and fall back
  to a company route

Multiple values for one person in the Contacts export are deduplicated and
separated with semicolons. Phone numbers retain their international `+` prefix.
A person may appear with no email, phone, or LinkedIn route when only a
validated name/title was published; Contacts is intentionally a superset of the
people chosen as lead primaries.

## Run the full configured scrape

The commands below are written for a Linux shell. On Windows, run them inside
WSL2 rather than native PowerShell.

### 1. Install and start the services

Requirements: Python 3.11+, GNU Make, Docker, Docker Compose, and `curl`.

```bash
cp .env.example .env
make install
docker compose up -d postgres redis temporal
make migration-check
```

Start the API locally so you can create a workspace and campaign:

```bash
.venv/bin/python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Leave that process running and open a second terminal in the repository.

### 2. Create a workspace and campaign

Create a workspace:

```bash
curl -sS -X POST http://localhost:8000/workspaces/ \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-api-key" \
  -H "x-workspace-id: 00000000-0000-0000-0000-000000000000" \
  -d '{
    "name": "VA Lead Intelligence",
    "slug": "va-leads",
    "billing_email": "ops@example.com",
    "plan": "trial"
  }'
```

Copy the returned `id`, then create a campaign using that workspace ID:

```bash
curl -sS -X POST http://localhost:8000/campaigns/ \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-api-key" \
  -H "x-workspace-id: <workspace-uuid>" \
  -d '{
    "name": "ANZ VA leads",
    "status": "active",
    "capability_filter": ["virtual_assistant"],
    "score_threshold": 0.5
  }'
```

Copy the returned campaign `id` and set both values in the shell:

```bash
export WORKSPACE_ID="<workspace-uuid>"
export CAMPAIGN_ID="<campaign-uuid>"
```

You can reuse an existing workspace and campaign instead. Use a new workspace
when you need an isolated comparison with an earlier scrape.

### 3. Run the company sources

Run the three company-discovery sources explicitly. This avoids invoking the
website adapters without a domain list and avoids the empty `manual_seed`
source.

```bash
.venv/bin/python scripts/run_source_engine.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --source-keys openstreetmap finance_directory nz_finance_advisers
```

A successful run prints JSON containing `"status": "succeeded"`. Treat a
non-zero exit code or `"status": "failed"` as a failed scrape; do not export
that run as complete.

For a quick NZ-directory smoke test, limit its list pages:

```bash
.venv/bin/python scripts/run_source_engine.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --source-keys nz_finance_advisers \
  --query-overrides '{"nz_finance_advisers": {"max_list_pages": 2}}'
```

### 4. Drain the eligible domains for targeted contacts

This command takes a stable snapshot of eligible company domains, runs
`company_web` across three disjoint shards concurrently, and then uses
`team_pages` for domains where the first pass did not produce a persisted
contact hit:

```bash
.venv/bin/python scripts/extract_targeted_contacts.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --shards 3
```

Omitting `--max-domains` drains every currently eligible domain. For a quick
test, add `--max-domains 25`. The command exits non-zero if a shard fails.
Rerun the same command after a failure; stored hits are deduplicated and the
domain query is recalculated from the remaining incomplete contact coverage.

Three shards are the supported default. Increasing the count can make external
sites or the database the bottleneck and should be benchmarked before use.

### 5. Export the results

Run the export only after the company-source and contact-enrichment commands
have succeeded:

```bash
mkdir -p exports

.venv/bin/python scripts/export_leads_csv.py \
  --workspace-id "$WORKSPACE_ID" \
  --region anz \
  --min-rank medium \
  --leads-path exports/anz_remote_leads_with_contacts.csv \
  --primary-contacts-path exports/anz_primary_contacts.csv \
  --contacts-path exports/anz_contacts.csv \
  --companies-path exports/anz_all_companies.csv \
  --leads-alias-path exports/anz_remote_leads_with_targeted_contacts.csv \
  --companies-alias-path exports/anz_all_companies_targeted.csv
```

Open `exports/anz_remote_leads_with_targeted_contacts.csv` for the complete
lead list, `exports/anz_primary_contacts.csv` for one selected person per lead,
and `exports/anz_contacts.csv` for the complete person-level view.
Re-running the export replaces those files from the current database state.

### 6. Build the readable workbook

Build the workbook from the four canonical CSVs:

```bash
.venv/bin/python scripts/build_leads_workbook.py
```

This writes
`exports/anz_full_leads_with_targeted_contacts.xlsx` with these sheets:

| Sheet | Contents |
|---|---|
| `Leads` | Prospecting view with one row per lead/contact association, so every company-linked email, phone, and LinkedIn profile is directly visible; leads repeat when a company has multiple people |
| `Primary Contacts` | Exactly one row per lead with its selected person or an explicit unavailable status |
| `Contacts` | One row per validated person found in company or source-hit routes, including people not chosen as lead primaries, with all associated identifiers |
| `Companies` | One row per company with its best company routes and selected named-contact routes |

The builder validates the exact CSV headers and ID consistency before writing,
freezes the header row, enables filters, keeps contact values as text, and uses
compact non-wrapped rows. The visible columns are human-first. Technical IDs
and raw mapped coordinates remain in hidden columns at the far right, and
single LinkedIn/form/source URLs are clickable. The workbook joins existing
lead and contact rows only; it does not re-score or re-match them. Missing,
unreadable, malformed, or relationally inconsistent inputs make it exit with
status 2 without replacing the workbook. An older workbook may still exist and
must not be treated as current. Rerun the complete export instead of repairing
CSV headers or references manually.

## Safe reruns and partial runs

- Reuse the same workspace to continue enriching or refresh its source data.
  Source hits are deduplicated by content hash.
- Use a new workspace and campaign for a clean, isolated comparison. This is
  safer than deleting an existing dataset.
- Run one company source with `--source-keys <source>` when diagnosing it.
- Use `--max-domains` only for a bounded contact-enrichment test. Omit it for
  the full configured drain.
- Do not treat an export as current until both preceding phases succeeded.

See [Crawler operations](docs/runbooks/crawler-operations.md) for failure and
rerun checks.

## How scoring works

Directory and OpenStreetMap records use `company_existence_only`: the company
exists in a target sector, but no hiring intent is claimed. The exporter scores
sector fit, remotely delegable workload, role signals, and usable contact
routes.

- **High**: score 75+ and has a usable email, phone, or actionable form URL.
- **Medium**: score 55–74, or a 75+ score without a usable route.
- **Low**: score below 55.

Each lead includes an `explanation` column describing the signals used. The
current sector mapping is explained in
[How VA leads are generated](docs/user-guide/how-leads-are-generated.md).

## Expand to other industries or areas

The simplest expansion path is OpenStreetMap because its areas and business
tags are configuration-driven.

### Add another industry

1. Find the real OpenStreetMap key/value used by that business type.
2. Add one entry under `sources.openstreetmap.adapter_config.tags` in
   `config/sources/source-registry.yaml`. Supply a clear synthetic `title` and
   `category` describing the VA-relevant workload.
3. Add the new sector vocabulary to `CATEGORY_PATTERNS` and its explanation to
   `VA_USE_CASES` in `scripts/export_leads_csv.py`. Without this, the exporter
   may classify the new records as `Other` and filter them out.
4. Add focused adapter and export tests in `tests/test_source_engine_extra.py`
   or `tests/test_source_engine.py`.
5. Run the validation commands below, then perform a small source run before a
   full scrape.

Prefer expanding these existing configuration and classification surfaces over
creating a new adapter. Add a new adapter only when the source is genuinely
different—for example, a sector-specific public directory with its own
pagination and profile structure.

### Change the geographic target

Edit `sources.openstreetmap.adapter_config.areas` in
`config/sources/source-registry.yaml`. The values are OpenStreetMap area names.
The current values are the whole named areas `Australia` and `New Zealand`.

If the new output is outside ANZ, export with `--region all`. The existing
`--region anz` filter intentionally keeps only Australia/New Zealand location
signals. Review location normalization, category language, phone formatting,
and tests before claiming support for another country.

### Expand official-site contact coverage

`company_web` and `team_pages` enrich domains already discovered by a company
source; they do not discover a new market by themselves. To increase named
contacts in another industry, first add or import the companies, ensure their
official domains resolve correctly, then run the same three-shard enrichment
and export phases.

For a curated list, place a CSV or JSON file under
`$MANUAL_SEED_DIR/<workspace-uuid>/` and run `manual_seed` with a sandboxed
relative `path` override:

```bash
export MANUAL_SEED_DIR="$PWD/data/manual_seed"

.venv/bin/python scripts/run_source_engine.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --source-keys manual_seed \
  --query-overrides '{"manual_seed": {"path": "companies.csv"}}'
```

In this example the file is
`data/manual_seed/$WORKSPACE_ID/companies.csv`. Accepted fields are listed under
`sources.manual_seed.allowed_fields` in the source registry.

## Validation

Before committing a configuration, scoring, or runtime change:

```bash
make lint
make typecheck
make test
make config-validate
make benchmark
make handover
```

`make handover` is the complete production-readiness gate and also detects
generated-model drift.

## Source reference

| Source | Purpose | Configured bound |
|---|---|---|
| `openstreetmap` | Discover ANZ businesses in configured sectors | 16 tags across Australia and New Zealand; node records only |
| `finance_directory` | Discover Australian finance profiles | 1,200 profile pages |
| `nz_finance_advisers` | Discover NZ adviser/provider profiles | 30 list pages |
| `company_web` | Find contact routes on known official domains | 6 pages/domain, depth 2, 30 seconds/domain |
| `team_pages` | Find named people and person-linked routes | Public team/about/contact paths, 30 seconds/domain |
| `manual_seed` | Import a curated CSV or JSON list | File must be inside `MANUAL_SEED_DIR` |

Source limits, allowed fields, and adapter settings live in
`config/sources/source-registry.yaml`. Architecture details are in
[Source engine data flow](docs/architecture/source-engine-data-flow.md) and
[Source access matrix](docs/architecture/source-access-matrix.md).

## Development commands

```bash
make help
make test
make lint
make typecheck
make config-validate
make migration-check
make benchmark
make contracts
make handover
```

The API documentation is available at `http://localhost:8000/docs` while the
API is running. `spec/domain.yaml` is the canonical source for generated domain
models and API contracts.
