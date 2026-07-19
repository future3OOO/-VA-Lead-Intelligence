# Source Access Matrix

| Source | Access Mode | Data Collected | Rate Limit | API Key / Credential | Kill Switch |
|--------|-------------|----------------|------------|--------------------|-------------|
| manual_seed | manual_import | company_name, title, body, contact_routes | none | none | `sources.manual.enabled` |
| greenhouse_jobs | public_api | job postings: title, location, description, apply URL | 2 req/s | none | `sources.greenhouse.enabled` |
| lever_jobs | public_api | job postings: title, location, description, apply URL | 2 req/s | none | `sources.lever.enabled` |
| ashby_jobs | public_api | job postings: title, location, description, job URL | 2 req/s | none | `sources.ashby.enabled` |
| smartrecruiters_postings | public_api | job postings: title, location, description, apply URL | 2 req/s | optional X-SmartToken | `sources.smartrecruiters.enabled` |
| company_web | scoped_public_web_crawl | HTML text, JSON-LD Organization, emails, phones, sales forms | 2 req/s, max 8 pages | none | `sources.company_web.enabled` |
| search_discovery | licensed_api | search result URLs, titles, snippets | 1 req/s | Google CSE or SerpAPI key | `sources.search_discovery.enabled` |
| openstreetmap | public_api | real ANZ business name, address, phone, email, website, business category | 0.2 req/s | none | `sources.openstreetmap.enabled` |
| team_pages | scoped_public_web_crawl | named people, job titles, emails, phones, LinkedIn from `/team`/`/about`/`/people` pages | 2 req/s, max 8 pages | none | `sources.team_pages.enabled` |
| hunter_domain | licensed_api | domain emails, positions | 1 req/s | Hunter.io API key | `sources.hunter.enabled` |

## Prohibited Access Modes

The following are never used by this source engine:

- Authenticated scraping against a site's terms of service
- CAPTCHA bypass
- Fake account creation
- Bulk stealth collection
- Robots.txt or paywall evasion

All web sources check `robots.txt` and respect rate limits.
