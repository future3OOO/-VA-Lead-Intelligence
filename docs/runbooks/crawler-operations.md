# Crawler Operations Runbook

## Scope

Crawlee service under `services/crawler/` and source health.

## Common Issues

- **Rate limited**: Increase `rate_limit_rpm` or pause source in source policy.
- **Robots disallowed**: Confirm `do_not_scrape_if_robots_disallow` is true and source is public.
- **Stale snapshots**: Trigger a Temporal `CrawlWorkflow` manually via `tctl`.

## Monitoring

- Check `source_health` records for `healthy=false`.
- Review Temporal `crawl_sources` activity failures.

## Tuning

Adjust `config/source-policy/default.yaml` TTLs and rate limits, then run `make config-validate`.
