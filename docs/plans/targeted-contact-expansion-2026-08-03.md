# Targeted Contact Expansion — 2026-08-03

## Authority and objective

- Source of truth: the user request in this session, repository contracts on `main`, and the public behavior of the source-engine adapters/exporter.
- Trusted base: `origin/main` at `54caf449950344c7c990731952753e059ec53469`.
- Target branch: `codex/contact-expansion-sharded` in `/mnt/c/tmp/va-lead-intelligence-contact-expansion`.
- Objective: increase safely matched named contacts, direct emails, phones, and LinkedIn profiles across every exported sector, then run the website backfill across three deterministic concurrent shards.
- Conflict rule: preserve person/contact evidence and company identity accuracy over raw match count; ambiguous data remains generic or blank.

## Scope

In:

- Broader person-card and structured-data extraction from official company websites, including real estate/property management, administration, legal, accounting, insurance, finance, and trades.
- Same-card person/email/phone/LinkedIn association and canonical LinkedIn profile handling.
- Role-aware deterministic contact selection for generic sector lead titles.
- One replacement targeted-contact backfill CLI that snapshots eligible domains, partitions them into three disjoint shards, runs each phase concurrently, and fails if any shard fails.
- Focused behavior tests, operator documentation, full validation, clean scrape, export, and accuracy/performance audit.

Out:

- LinkedIn account automation, search-result scraping, guessed email addresses, or third-party enrichment providers.
- Database schema, API schema, scoring bands, company resolution, source policy, SSRF/redirect validation, robots handling, and per-host rate limits.
- Changes to OpenStreetMap, finance-directory ingestion, NZ adviser directory ingestion, Temporal placeholders, deployment, or infrastructure.

## Delivery map

- PR count / stack depth: one PR, depth 1.
- Owner branch: `codex/contact-expansion-sharded` owns extraction, selection, sharded execution, tests, docs, and regenerated exports.
- Commit structure:
  1. Expand official-site person extraction and role-aware matching with vertical RED/GREEN tests.
  2. Replace the two duplicated missing-contact scripts with the three-shard backfill CLI, tests, and docs.
  3. Add reproducible clean-scrape exports only after the code and full gates pass.
- Human-authored changed-code budget: <=1,000 additions plus deletions, excluding tests, docs, and generated CSVs.
- Scope breaker: if human-authored code exceeds 1,000 changed lines or the sharded CLI cannot remain independent of runner/persistence changes, move sharding into a second PR before publishing.
- Consolidation rule: do not create more branches; if either slice requires shared runner/schema changes, stop and revise this plan rather than stacking fixes.
- Deploy freeze: do not merge or run against a production database until the clean disposable-database scrape and exact-head reviewer gate pass.

## Affected surface and contracts

- Changed boundary: `team_pages._extract_from_soup` and the `company_web` reuse path that turns one official website page into evidence-bound contact routes.
- Changed operator boundary: the missing-contact backfill command and its deterministic domain partition.
- Changed export boundary: `_lead_named_contact` / `_best_named_contact` choose the strongest role-relevant person without borrowing another person's details.
- Upstream callers: `TeamPagesAdapter.fetch`, `CompanyWebAdapter._crawl_domain`, and the targeted-contact backfill CLI.
- Adjacent consumers: `enrich_contact_routes`, `SourceRunner._persist_hit`, company contact-route persistence, and both targeted CSV exports.
- No-change surfaces requiring proof: `SourceRunner.run` signature/status/counters, company/workspace isolation, source-hit upsert replay, resolver franchise/shared-domain behavior, contact normalization, generic company contacts, scoring/ranks, SSRF/redirect/robots/per-host limiting, API schemas, and existing six-source registry.
- Authoritative contact contract: a named email, phone, or LinkedIn URL is exported only when official-site structure explicitly associates it with that person; page-level office contacts remain generic.
- Shard invariants: the domain snapshot is deterministic; each domain appears in exactly one shard; three-shard union equals the unsharded snapshot; empty shards are safe; reruns are idempotent; any failed shard makes the command fail.

## Module shape

- Public extraction interface: `_extract_from_soup(soup, base_url, domain)`; deepen the existing module rather than add another parser.
- Public selection interface: `contact_selection.select_lead_person(...)`; keep the exporter thin while one deep module hides route parsing, validation, role matching, and deterministic ranking.
- Public operator interface: one targeted-contact backfill CLI replacing `extract_team_pages_missing.py` and `extract_company_web_missing.py`.
- New CLI justification: it replaces two duplicated SQL/runner scripts and hides a real two-phase, three-shard orchestration and failure-aggregation workflow.
- New selection-module justification: the production gate identified an already oversized exporter; moving the cohesive 337-line selection policy behind four stable functions reduces that file and creates a real testable seam instead of another wrapper.
- Rejected shallow paths: a wrapper around the two old scripts, a standalone sharder utility, parser duplication in `company_web`, sharding inside `SourceRunner`, or leaving selection mixed into CSV rendering.
- Test surface: official HTML fixtures through `_extract_from_soup`, route-order-independent lead selection, shard partition properties, concurrent phase execution, and failure propagation.

## Verification gates

- RED/GREEN per behavior slice with focused pytest commands.
- `make lint`
- `make typecheck`
- `make test`
- `make config-validate`
- `make migration-check`
- `make benchmark`
- `make contracts`
- `make handover`
- Production-code quality gate against `origin/main`.
- Clean disposable-database full scrape, repeated deterministic export, and audit by sector for named/email/phone/LinkedIn gains plus zero mismatches.
- Runtime comparison: one-shard versus three-shard deterministic fixture/harness, and actual three-shard wall-clock reporting.
- Exact-head CI and reviewer-thread completion gate before merge readiness.

## Execution checklist

- [x] Create clean worktree from trusted `main` and run repository intake.
- [x] Map extraction, persistence, export, API, and concurrency blast radius.
- [x] Record baseline sector/contact coverage and root-cause hypotheses.
- [x] Complete preflight and first extraction RED/GREEN slice.
- [x] Add structured-card/nested-data/LinkedIn extraction slices with negative association tests.
- [x] Add role-aware deterministic selection with ambiguity/no-borrowing tests.
- [x] Replace duplicated backfill scripts with three-shard orchestration and property/failure tests.
- [x] Re-walk affected/no-change surfaces and run focused plus full gates.
- [x] Run clean three-shard scrape, export, accuracy audit, and runtime reporting.
- [x] Run independent precommit challenge, production quality gate, and cleanup.
- [ ] Commit, push, open/update the owning PR, and close the exact-head reviewer loop.

## Self-critique incorporated

- Kept the work to one PR because all three changes are required by one backfill/output workflow, but added a hard 1,000-line scope breaker.
- Named the sharding home as the replacement operator CLI; no unnamed utility or runner change.
- Added explicit idempotency, partial-shard failure, total/disjoint partition, and office-contact negative proof.
- Preserved one extraction implementation reused by both website adapters.

## Clean-run evidence

- Discovery completed without source errors: OpenStreetMap 2,751 hits, Finance Directory 809 hits, and all 30 NZ Finance Advisers list pages with 2,998 extracted records.
- Official-site enrichment covered 1,518 eligible domains in three disjoint 506-domain shards; the final missing-domain recovery covered 1,510 domains in 840.27 seconds across 504/503/503-domain shards.
- Deterministic exports contain 4,174 leads and 4,060 companies. Repeated exports were byte-identical.
- Named-contact coverage increased from 841 to 1,108 leads; the new targeted lanes contain 61 direct emails, 143 person phones, and 87 personal LinkedIn profiles.
- Final audit found zero malformed contact fields, false organisation/page-label contacts, prohibited-domain merges, or High-ranked leads without a usable contact route.

## Execution handoff

Use this artifact as the governing plan; do not create or re-plan another plan. Continue under `repo-large-implementation`, `production-preflight`, and `production-code`. Keep this checklist current, stay below the 1,000-line code budget, re-walk the real affected surface before edits and completion, and publish only after the clean scrape and reviewer gate pass.
