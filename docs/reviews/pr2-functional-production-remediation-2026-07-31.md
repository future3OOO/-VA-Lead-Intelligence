# PR #2 Functional Production Remediation

## Authority and delivery

- Authority order: `AGENTS.md` → this governing artifact → canonical `spec/domain.yaml` and
  migrations → exact PR-head code/tests/exports → review findings. This artifact governs
  implementation order; update it before coding if those authorities conflict.
- Trusted base: `origin/main`.
- Target: PR #2, branch `devin/source-engine`, checkout
  `C:\tmp\va-lead-intelligence-pr2-95db74c`, starting head
  `e31ecc8c825bba719926c0f0df30e88b97c4f7ef`.
- Startup gate completed: fetched `origin/devin/source-engine`, verified GitHub and local HEAD match,
  and confirmed the checkout is clean, attached, and non-detached.
- Implementation owner: Codex in the named checkout only.
- One existing PR owns the coupled resolver, enrichment, export, CLI, tests, and docs changes.
- Commit structure:
  1. identity/contact RED-GREEN tests and runtime fix;
  2. deterministic/truthful export plus CLI RED-GREEN tests and fix;
  3. documentation and regenerated exports.
- Human-authored remediation budget from the starting head: identity/contact ≤450 lines,
  export/CLI ≤450, tests/docs ≤350; hard stop before 1,300 total changed code lines. The existing
  token list will not be extended; structural evidence will own acceptance. Its wholesale removal
  is deferred unless the remaining budget safely permits it.
- Stack depth: one. Do not open another PR; consolidate if this slice cannot remain coherent.
- Deploy/merge freeze: do not merge PR #2 until the checklist and reviewer gate are complete.

## Scope

In:

- branch-safe company identity and contact isolation, including shared corporate domains;
- evidence-based named contacts and strict person/email association;
- deterministic export selection and truthful inferred-fit scoring/explanations;
- extraction CLI target/limit validation;
- focused regression tests, operator documentation, exports, and PR-thread closure.

Out:

- compliance expansion, new sources, wider crawling, unrelated model refactors, or UI work.
- private/production databases, secrets, runtime configuration, cache/reference worktrees, generated
  contracts except through the canonical generator, and unrelated branches.

Mutable paths: `src/services/source_engine/{resolver,enricher,runner}.py`,
`src/services/source_engine/adapters/team_pages.py`, `scripts/export_leads_csv.py`, the four
`scripts/extract_{team_pages,company_web}{,_missing}.py` CLIs, their tests, one focused migration,
README/operator docs, this artifact, and generated exports.

## Affected surface and contract

Public surfaces: `resolve_company`, `enrich_contact_routes`, team-page normalization, CSV export,
and the four bounded extraction CLIs.

Adjacent consumers: `SourceRunner._persist_hit`, `ContactRoute` persistence, company/contact CSV
joins, manual-seed intent classification, config/contracts generation, and source-run failure
status.

Contract:

1. A source listing must deterministically resolve to one company without pooling contacts from a
   different branch.
2. A named contact requires person evidence; a named email must match the same person.
3. Company-fit inference must remain useful but must not be described as an observed job, buyer
   intent, or workplace arrangement.
4. Operator limits and workspace/campaign targets must be explicit and honored exactly.

No-change proof: prohibited-domain filtering, six-source registry, manual-seed intent, High-rank
contact requirement, content-hash idempotency, generator drift guard, and failed-run exit status.

Branch identity will deepen the existing resolver through the existing `CompanyIdentifier` model:
stable `(workspace, source, source_native_id)` identity is authoritative; domain plus normalized
name may reuse the same company, but a shared domain alone may not. Domain-only enrichment is
allowed only when exactly one company candidate exists; ambiguity fails closed without attaching
contacts.

Named-contact acceptance: structured `Person` data, a LinkedIn person profile, or same-card contact
evidence only; never standalone headings. Generic addresses remain company routes. Named email
matching requires full normalized first/last-name or initial patterns, never arbitrary substrings.

Deterministic ordering: verified/named routes before generic routes, then normalized value; lead
ties by score, newest source timestamp, source ID/URL. Database reads must use matching `ORDER BY`,
and two repeated exports from unchanged state must be byte-identical.

## Persistence system

- Authoritative records: `Company`, `CompanyIdentifier`, `SourceHit`, `ContactRoute`, `SourceRun`.
- Mutation boundary: `SourceRunner._persist_hit()` through company resolution, hit association,
  and contact enrichment.
- Interleavings: concurrent/repeated runs, same domain with different branches, name-only hits,
  enrichment after branch discovery, and conflict/no-op insertion paths.
- Invariants: reruns are idempotent; one source listing has one stable company; shared domains do
  not pool branch contacts; concurrent identity creation resolves to one winner.
- Proof: sequential, replay, shared-domain, ambiguous-enrichment, and concurrent integration tests.

Historical-data gate: determine whether the committed Elders/Bairnsdale contamination is stale
workspace state or current extraction. Export acceptance requires a clean local/test workspace
with migrations applied and the source tables rebuilt. No private or production database may be
reset. If a clean rebuild cannot be produced, mark export verification blocked and do not call the
PR merge-ready.

## Verification

- Focused RED/GREEN tests for shared-domain branches, stable source identity, false headings
  (`Entry Requirements`, `Lj Hooker Coomera`, `Solar Vents`, `Routine Inspections`, `Broome Wa`,
  `Prd Whitsunday`),
  short-substring email mismatches, inferred-fit explanations, deterministic selection, and CLI
  bounds.
- Branch contamination fixture: Bairnsdale must never receive Hornsby/Queensland contacts.
- CLI acceptance: `--max-domains 0` performs no crawl, negatives fail argument parsing, and all four
  scripts require explicit workspace and campaign IDs.
- `make lint`, `make typecheck`, `make test`, `make config-validate`,
  `make migration-check`, `make benchmark`, `make contracts`, `make handover`.
- Regenerate and audit both committed CSVs from the mandatory clean-database run; run the exporter
  twice and compare bytes.
- Verify exact-head CI, merge state, checks, and unresolved non-outdated review threads after push.

Clean-run evidence: the bounded live directory run fetched 68 hits, qualified 42, deduplicated 26,
and completed with zero errors. A later wider 1,200-profile/15-page attempt failed closed with two
source errors and no partial hits, demonstrating failure reporting without changing the accepted
clean dataset.

## Execution checklist

- [x] Reproduce and trace each functional defect from committed CSV rows and direct function probes.
- [x] Realign the implementation checkout to the live PR head.
- [x] Critique and correct this governing artifact.
- [x] Add focused failing behavior tests and record RED for identity, contact evidence, scoring,
  and deterministic selection.
- [x] Fix company identity and contact isolation; prove replay, ambiguous enrichment, migration,
  and the concurrent winner path.
- [x] Fix named-contact evidence and person/email association.
- [x] Make export selection deterministic and inferred-fit language truthful.
- [x] Fix extraction CLI bounds and explicit targets.
- [x] Stop extending the deny list; make structural evidence the acceptance boundary and correct
  stale documentation.
- [x] Run focused local verification, migration upgrade, PostgreSQL concurrency interleavings,
  lint, typecheck, config, benchmark, contracts, and generator-format drift checks; full pytest
  remains assigned to exact-head CI because the local fixture hard-codes unrelated DB credentials.
- [x] Regenerate and independently audit exports from the isolated clean database; repeated files
  are byte-identical.
- [x] Run production-code quality and two focused final diff challenges; reject the stale matcher
  finding against the live function test, prove zero bounds directly, and prove both concurrency
  loser paths.
- [ ] Commit and push PR #2.
- [ ] Record pushed SHA; re-query exact-head CI, merge state, and review threads.
- [ ] Resolve current generator threads only after the pushed fix is green.

Regroup rule: the existing `CompanyIdentifier` boundary and one uniqueness migration are authorized.
Any additional schema/public API or projected remediation above 1,300 changed code lines requires
updating this artifact and stopping before that expanded edit.

## Execution handoff

Do not create a new plan or re-plan this pass. Follow and update this checklist. Use
`repo-large-implementation`, `production-preflight`, diagnose/TDD, and `production-code`; re-walk
the affected surface before edits and completion. Do not touch reference/private-runtime paths.
Commit and push before resolving threads, and do not merge until the freeze gate is cleared.
