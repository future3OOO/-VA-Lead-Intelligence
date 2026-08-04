# How VA Leads Are Generated

This guide explains what a row in the lead export means. For exact setup and
run commands, use the [root README](../../README.md#run-the-full-configured-scrape).

## What the system is looking for

The system looks for Australian and New Zealand service businesses whose
normal work creates repeatable administrative tasks. It does not require an
advertised vacancy and does not claim that a listed business is hiring.

The checked-in configuration targets:

| Business sector | Typical work that can be delegated remotely |
|---|---|
| Property management and real estate | Listing administration, CRM updates, tenant/buyer follow-up, appointments, and rent-roll data entry |
| Accounting, bookkeeping, and tax | Client files, data entry, invoicing, reconciliations, inbox/CRM work, and compliance paperwork |
| Insurance, mortgage, and financial advice | Claims or loan files, scheduling, client enquiries, CRM updates, and documentation |
| Legal services | Client intake, document preparation, diary management, billing administration, and filing |
| Trades, construction, and home services | Job scheduling, dispatch, invoicing, customer follow-up, and maintenance coordination |
| Administrative offices | General business support and coordination |

These sectors are a deliberate starting scope, not a claim that they are the
only industries suited to virtual assistants.

## Where the data comes from

The discovery phase uses:

- OpenStreetMap business nodes in the named areas `Australia` and `New Zealand`
- a bounded Australian finance-professional directory
- a bounded New Zealand financial-adviser directory
- optional CSV or JSON manual seeds

The enrichment phase visits official domains already associated with those
companies. It searches bounded company, contact, team, about, people, and
leadership pages for published email addresses, phone numbers, forms, named
people, and person-linked LinkedIn URLs.

The system does not crawl LinkedIn to discover people. A LinkedIn URL is only
exported as a named route when it is published on the source or official company
website and can be associated with that person.

## Why coverage is not exhaustive

A full configured run is still narrower than the whole ANZ market:

- OpenStreetMap only returns businesses present as nodes with one of the 16
  configured tags.
- Directory sources have page limits.
- A company needs a usable official domain before its website can be enriched.
- Websites may omit staff details, block crawling, time out, or publish generic
  office routes only.
- Contact validation rejects malformed or ambiguous person/email associations.

Blank named-person fields therefore mean “no validated published route was
found,” not “the company has no relevant staff.”

## How a source record becomes a lead

1. An adapter normalizes a public listing into a source hit.
2. The resolver creates or links the correct company and keeps distinct
   branches separate where the evidence supports it.
3. Contact routes are normalized and assigned either to a named person or to
   the company.
4. The exporter filters to the requested geography and target sectors.
5. The exporter scores, ranks, deduplicates, and explains each lead.

OpenStreetMap and directory rows use the intent label
`company_existence_only`. Their synthetic `job_title` describes the likely VA
workload for the sector; it is not an observed job advertisement.

## Scores and ranks

- **High**: score 75 or above and at least one usable email, phone, or contact
  form URL.
- **Medium**: score 55–74, or a 75+ score without a usable contact route.
- **Low**: score below 55.

The `explanation` column states the sector, workload, and contact evidence used
for the result. Rankings are prospecting priorities, not guarantees of demand.

## Contact columns

The complete lead export deliberately separates person-level and company-level
routes:

| Column group | Meaning |
|---|---|
| `named_contact_*` | Name, title, email, phone, and LinkedIn explicitly associated with the selected person |
| `company_*` | Generic office email, phone, or contact form |
| `best_*` | Named route first, then the company route as a fallback |

Use `anz_named_contacts.csv` when you want one readable row per validated
person. Use `anz_remote_leads_with_targeted_contacts.csv` when you want every
ranked lead with both targeted and generic contact lanes.

## Expanding the scope

Other industries can use the same pipeline when their normal operations create
delegable administrative work.

For an OpenStreetMap-backed expansion:

1. Add the real business tag, synthetic workload title, and category under
   `sources.openstreetmap.adapter_config.tags` in
   `config/sources/source-registry.yaml`.
2. Teach `scripts/export_leads_csv.py` how to recognize and explain the new
   category.
3. Add focused source and export tests.
4. Run a small source query, inspect false positives and contact quality, then
   run the full configured scrape.

Change `sources.openstreetmap.adapter_config.areas` to narrow or extend the
geographic search. For countries outside Australia and New Zealand, export with
`--region all` and review the location and phone assumptions before describing
the new country as supported.

Official-site enrichment is reusable across industries, but it only enriches
companies already discovered or manually seeded. See
[Expanding industries or areas](../../README.md#expand-to-other-industries-or-areas)
for the exact files and validation commands.
