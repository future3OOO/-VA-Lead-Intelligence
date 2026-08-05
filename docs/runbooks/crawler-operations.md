# Source Scrape Operations Runbook

Use this runbook to operate, resume, and verify the source scrape. The
[root README](../../README.md#run-the-full-configured-scrape) contains the full
first-time setup and copy/paste commands.

## Definition of a complete run

A current workbook requires all four steps to succeed for the same workspace:

1. `openstreetmap`, `finance_directory`, and `nz_finance_advisers`
2. `extract_targeted_contacts.py --shards 3` with no `--max-domains` limit
3. `export_leads_csv.py` after phases 1 and 2 finish
4. `build_leads_workbook.py` from the four canonical CSV exports

The result is a full run of the checked-in bounds. It is not an exhaustive list
of all Australian and New Zealand companies.

## Pre-run checks

```bash
docker compose ps
.venv/bin/python scripts/run_source_engine.py --help
.venv/bin/python scripts/extract_targeted_contacts.py --help
.venv/bin/python scripts/export_leads_csv.py --help
.venv/bin/python scripts/build_leads_workbook.py --help
```

Confirm that:

- Postgres is healthy.
- `WORKSPACE_ID` and `CAMPAIGN_ID` belong to the same workspace.
- the workspace is new if the purpose is a clean comparison.
- no `--max-domains` flag will be used for the final contact drain.

## Run and record each phase

### 1. Company discovery

```bash
set -o pipefail

.venv/bin/python scripts/run_source_engine.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --source-keys openstreetmap finance_directory nz_finance_advisers \
  | tee source-run.log
```

Proceed only when the output reports `"status": "succeeded"` and the process
exits zero. Record `source_run_id`, hit totals, qualified totals, duplicate
totals, and error totals.

### 2. Targeted-contact drain

```bash
set -o pipefail

.venv/bin/python scripts/extract_targeted_contacts.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --shards 3 \
  | tee targeted-contact-run.log
```

The command runs three concurrent database/source-run shards. Keep the printed
per-shard run IDs and counts. Do not start the export while any shard is still
running.

### 3. Export

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

### 4. Build the workbook

```bash
.venv/bin/python scripts/build_leads_workbook.py
```

The output is
`exports/anz_full_leads_with_targeted_contacts.xlsx`. It contains `Leads`,
`Primary Contacts`, `Contacts`, and `Companies` sheets sourced directly from
the four canonical CSV files. `Leads` expands each normalized lead to one row
per company contact so person-specific email, phone, and LinkedIn values are
immediately extractable. `Primary Contacts` stays one row per lead. Raw join
IDs and mapped coordinates are retained in hidden columns at the far right.
Generated CSV and XLSX files remain local under `exports/`; they are ignored by
Git.

The builder exits with status 2 without replacing the workbook if any CSV is
missing, unreadable, malformed, or does not join consistently by ID. An older
workbook may still exist and must not be treated as current. Rerun the complete
export; do not repair generated headers or references manually.

## Resume after a failure

Do not delete the workspace. Fix the failing dependency or source, then rerun
the failed phase with the same IDs.

- Source hits use content-hash deduplication.
- Contact enrichment rebuilds its candidate list from domains with incomplete
  person-contact lanes.
- The export is deterministic for the current database state and replaces the
  requested output files.

If a source repeatedly fails, run it alone to isolate the problem:

```bash
.venv/bin/python scripts/run_source_engine.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --source-keys openstreetmap
```

For a bounded diagnostic—not a final drain—use:

```bash
.venv/bin/python scripts/extract_targeted_contacts.py \
  --workspace-id "$WORKSPACE_ID" \
  --campaign-id "$CAMPAIGN_ID" \
  --shards 3 \
  --max-domains 25
```

## Common failures

| Symptom | Action |
|---|---|
| Source run reports `failed` | Read `errors_total`, rerun that source alone, and do not export as complete |
| Overpass timeout or rate limit | Retry later; the adapter already uses bounded rates and two endpoints |
| Finance source discovers no profiles | Check source availability and robots response; do not substitute fabricated data |
| Contact shard fails | Rerun the complete contact command with the same IDs; completed hits remain deduplicated |
| Contact fields remain blank | The website may not publish a validated person-linked route; retain the separate company route |
| Export is unexpectedly small | Confirm the correct workspace, `--region`, `--min-rank`, and successful upstream phases |

Do not increase configured request rates as the first response to rate limiting.
Faster runs should come from the supported three-shard contact command and from
measured adapter concurrency changes with tests.

## Post-run verification

Check that all seven files exist and are non-empty:

```bash
for file in \
  exports/anz_remote_leads_with_contacts.csv \
  exports/anz_remote_leads_with_targeted_contacts.csv \
  exports/anz_primary_contacts.csv \
  exports/anz_contacts.csv \
  exports/anz_all_companies.csv \
  exports/anz_all_companies_targeted.csv \
  exports/anz_full_leads_with_targeted_contacts.xlsx; do
  test -s "$file" || { echo "Missing or empty: $file" >&2; exit 1; }
done

wc -l \
  exports/anz_remote_leads_with_contacts.csv \
  exports/anz_remote_leads_with_targeted_contacts.csv \
  exports/anz_primary_contacts.csv \
  exports/anz_contacts.csv \
  exports/anz_all_companies.csv \
  exports/anz_all_companies_targeted.csv

test -s exports/anz_full_leads_with_targeted_contacts.xlsx
```

Confirm each alias is byte-identical to its canonical export:

```bash
cmp exports/anz_remote_leads_with_contacts.csv \
  exports/anz_remote_leads_with_targeted_contacts.csv
cmp exports/anz_all_companies.csv \
  exports/anz_all_companies_targeted.csv
```

Open the complete lead, Primary Contacts, and Contacts files. Spot-check:

- named emails, phones, and LinkedIn URLs belong to the displayed person
- generic office routes stay in company fields
- phone and email columns contain clean values rather than page text
- High leads have a usable email, phone, or form
- locations are in the intended export region
- franchise branches and offices are not incorrectly merged

When comparing runs, record the workspace, commit SHA, source run IDs, source
counts, enrichment counts, export row counts, and file hashes. Compare like for
like; a bounded `--max-domains` test is not a valid baseline for a full drain.
