# How VA Leads Are Generated

This guide explains, in plain language, how this platform turns public business data into a ranked list of Australian and New Zealand companies that are likely to need a virtual assistant.

## 1. We start with a public business directory

The main source we use is **OpenStreetMap**. It is a free, public map and business directory. Businesses are listed with real names, addresses, phone numbers, emails, and websites.

We query OpenStreetMap for business categories that naturally create administrative work, such as:

- Real-estate agencies and property managers
- Accountants, bookkeepers, tax agents, and financial planners
- Insurance and mortgage brokers
- Law firms, conveyancers, and legal practices
- Builders, electricians, plumbers, painters, roofers, and other trade businesses
- Construction companies and home-service providers

We do **not** scrape LinkedIn, Google, or private directories. We do **not** use fake or purchased lists.

## 2. We match each business type to VA work

When OpenStreetMap tells us a business is, for example, an electrician, we do not just look for an advertised electrician job. Instead, we ask: *"What remote admin work does a busy electrical business usually need?"*

The answer is typically scheduling, dispatch, invoicing, customer follow-up, and maintenance coordination. So we label the business as a **Maintenance Coordinator / Electrical Services** lead.

The same logic applies to every business type:

| OpenStreetMap business type | Typical VA work |
|-----------------------------|-----------------|
| Real estate / property management | Listing admin, CRM updates, buyer/tenant follow-up, appointment scheduling, rent-roll data entry |
| Accounting / bookkeeping / tax | Client file admin, data entry, invoicing, reconciliations, inbox/CRM management, compliance paperwork |
| Insurance / mortgage broking | Claims/loan file processing, scheduling, customer enquiries, CRM updates, documentation |
| Legal / conveyancing | Client intake, document prep, diary management, billing admin, filing |
| Trades / construction / home services | Job scheduling, dispatch, invoicing, customer follow-up, maintenance coordination |

This is why we say the approach is **company-centric** rather than job-title-centric. We are looking at the business itself and deciding that it probably needs VA support, instead of only chasing specific job ads.

## 3. We score every lead from 0 to 100

Each lead is scored and ranked automatically:

- **High (75–100)** — strong fit. The business type clearly needs remote admin help, the work can be done remotely, and we have at least one contact route.
- **Medium (55–74)** — promising sector but the signal is weaker. For example, a job-board post from a target firm that is not itself a VA role.
- **Low (0–54)** — weaker fit, or a senior professional role the firm is hiring for directly.

Senior professional posts such as "Senior Accountant" or "Lead Lawyer" are pushed to the bottom or removed, because those are not VA roles.

## 4. We add a human-readable explanation

Every row in the export contains an `explanation` column. It looks like this:

> High fit (90/100): ABC Electrical (Home Services/Construction) in Brisbane, QLD is an OpenStreetMap business listing tagged as 'Maintenance Coordinator / Electrical Services'. Trade and home-service businesses with field staff need scheduling, dispatch, invoicing, and customer follow-up. Key signal: company/role is in the Home Services/Construction sector; role is a direct VA/admin function; description signals high administrative workload. Best contact: phone +61 400 123 456.

This means anyone can open the CSV and immediately understand why a company was selected.

## 5. We export everything into two CSV files

- `anz_remote_leads_with_contacts.csv` — one row per lead, with targeted person fields (`named_contact_name`, `named_contact_title`, `named_contact_email`, `named_contact_phone`, `named_contact_linkedin`), separate generic office fields (`company_email`, `company_phone`, `company_form`), and `best_*` fallback fields for compatibility.
- `anz_all_companies.csv` — one row per company, with the primary domain and all collected contact routes.

## 6. How to run it yourself

Make sure the local database is running:

```bash
docker compose up -d
```

Then fetch the latest OpenStreetMap listings:

```bash
python scripts/run_source_engine.py \
  --workspace-id 985cfd3b-a3af-4217-8b10-8c46b0915b92 \
  --campaign-id 2ddbdd5f-3e7e-4667-a3ca-4ee2dfb3bdfc \
  --source-keys openstreetmap
```

Finally, score and export the leads:

```bash
python scripts/export_leads_csv.py \
  --workspace-id 985cfd3b-a3af-4217-8b10-8c46b0915b92 \
  --region anz \
  --leads-path /tmp/anz_remote_leads_with_contacts.csv \
  --companies-path /tmp/anz_all_companies.csv
```

Change the `--leads-path` and `--companies-path` values to save the CSV files wherever you like.

## 7. Optional: get named hiring contacts

If you want named people rather than generic email addresses, you can run the bounded `team_pages` enrichment. It takes the domains found by OpenStreetMap, visits each company's own `/team`, `/about`, `/people`, or `/leadership` pages, and extracts real names, job titles, emails, phones, and LinkedIn profiles. It checks `robots.txt` first and only visits pages the site makes public.

```bash
python scripts/extract_team_pages.py \
  --workspace-id 985cfd3b-a3af-4217-8b10-8c46b0915b92 \
  --campaign-id 2ddbdd5f-3e7e-4667-a3ca-4ee2dfb3bdfc \
  --max-domains 100
```

Then export again and the `named_contact_*` columns will be filled where the company publishes them.

## 8. What about other sources?

The platform is built so you can add licensed or permissioned sources later (for example Hunter.io or a job-board API with an API key). OpenStreetMap and the optional `team_pages` enrichment are the default, free, no-API-key sources that get you started immediately.
