# Source Access Matrix

| Source | Access Mode | Data Collected | Rate Limit | API Key / Credential | Kill Switch |
|--------|-------------|----------------|------------|----------------------|-------------|
| `manual_seed` | manual_import | company_name, title, body, contact_routes | none | none | `sources.manual_seed.enabled` |
| `openstreetmap` | public_api | configured business nodes in the named areas Australia and New Zealand: name, address, phone, email, website, operator context, business category | 0.2 req/s | none | `sources.openstreetmap.enabled` |
| `finance_directory` | scoped_public_web_crawl | Australian finance-professional profile pages: company, website, phone | 3 req/s | none | `sources.finance_directory.enabled` |
| `nz_finance_advisers` | scoped_public_web_crawl | NZ FSPR adviser profiles and provider pages: adviser name, FAP, website, phone | 3 req/s | none | `sources.nz_finance_advisers.enabled` |
| `team_pages` | scoped_public_web_crawl | named contacts, job titles, emails, phones, LinkedIn profiles from `/team` and `/about` pages | 2 req/s | none | `sources.team_pages.enabled` |
| `company_web` | scoped_public_web_crawl | website contact routes and named people from priority pages | 2 req/s | none | `sources.company_web.enabled` |

## Prohibited Access Modes

The following are never used by this source engine:

- Authenticated scraping against a site's terms of service
- CAPTCHA bypass
- Fake account creation
- Bulk stealth collection
- Robots.txt or paywall evasion

All web-crawling sources (`team_pages`, `company_web`, `finance_directory`, and `nz_finance_advisers`) fetch and respect `robots.txt`. `openstreetmap` uses the public Overpass API and does not touch `robots.txt`. All sources respect rate limits.

The checked-in registry is the authority for current fields, bounds, and rate
limits. This matrix summarizes it; it does not imply exhaustive coverage of
either country or sector.
