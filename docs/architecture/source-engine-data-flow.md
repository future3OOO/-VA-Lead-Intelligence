# Source Engine Data Flow

The source engine transforms raw external signals into normalized, scored and resolvable lead opportunities.

## Pipeline

```
Source Registry / Query Library
        |
        v
SourceRunner -> BaseSourceAdapter.fetch()
        |
        v
normalize() -> SourceHit (dict)
        |
        v
classify_intent() -> IntentLabel
score_source_hit() -> priority
        |
        v
resolve_company() -> Company (if buyer-facing)
        |
        v
enrich_contact_routes() -> ContactRoute(s)
        |
        v
persist DBSourceHit + DBSourceRun
```

## Stages

1. **Portfolio selection**: `SourceRunner` reads `config/sources/source-registry.yaml` and loads the configured adapters.
2. **Fetch**: Each adapter calls its public API or scoped web crawl, governed by `RateLimiter`. The `openstreetmap` adapter queries the public Overpass API for real ANZ business listings by category.
3. **Normalize**: Raw payloads are mapped to the `SourceHit` contract, including `source_key`, `source_native_id`, `source_url`, `observed_at`, `published_at`, title/body, company/domain hints and `access_policy_version`. The `openstreetmap` adapter maps each business category (e.g. `office=estate_agent`, `craft=electrician`) to a VA-synthetic title and description of typical remote admin needs.
4. **Classify**: `classify_intent()` uses the `query-library` positive titles, task phrases and negative terms to produce an `IntentLabel`.
5. **Score**: `score_source_hit()` weights intent strength (35%), resolvability (20%), freshness (15%), evidence quality (15%), contactability (10%) and source stability (5%). The export script also applies a company-centric VA-fit score that favours target sectors, remote/hybrid work, admin-burden language, and available contact routes.
6. **Resolve**: `resolve_company()` matches an existing company by domain or canonical name, or creates a new one, but only for buyer-facing intents.
7. **Enrich**: `enrich_contact_routes()` persists routes found by the source (e.g. OpenStreetMap `website`/`email`/`phone` tags).
8. **Persist**: `DBSourceHit` and `DBSourceRun` are written; `content_hash` provides idempotency.

## Operational Controls

- **Rate limiting**: Token-bucket `RateLimiter` per adapter.
- **Concurrency**: `max_concurrency_per_host` caps parallel requests.
- **Kill switch**: Source registry `kill_switch` disables an adapter at runtime.
- **Checkpoint**: `CheckpointStore` records last observed time per adapter/workspace.
- **Metrics**: `SourceMetrics` captures hit, duplicate, qualified and error counts.
