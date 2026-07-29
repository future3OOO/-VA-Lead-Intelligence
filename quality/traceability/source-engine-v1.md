# DOD Traceability Report — Unknown

| Requirement | Title | Tests | Status | Evidence |
|-------------|-------|-------|--------|----------|
| SE-01 | Source adapter interface | 2 | passed | `test_source_registry_loads`, `test_manual_seed_adapter` |
| SE-02 | SourceHit contract | 2 | passed | `test_manual_seed_adapter`, `test_json_schema_export` |
| SE-03 | Intent classification | 2 | passed | `test_intent_classifier_buyer_request`, `test_intent_classifier_job_seeker` |
| SE-04 | Company resolution | 2 | passed | `test_resolve_company_creates_for_buyer`, `test_resolve_company_skips_seller` |
| SE-05 | Contact enrichment | 2 | passed | `test_resolve_company_creates_for_buyer`, `test_runner_manual_seed` |
| SE-06 | Source-level scoring | 4 | passed | `test_score_intent_values`, `test_score_source_hit_buyer_with_contact`, `test_high_fit_passes`, `test_low_fit_fails` |
| SE-07 | Operational controls | 3 | passed | `test_source_registry_loads`, `test_runner_manual_seed`, `test_score_determinism` |
| SE-08 | Jurisdiction and source policies | 5 | passed | `test_allowed_jurisdiction`, `test_blocked_jurisdiction`, `test_unknown_jurisdiction_uses_default`, `test_source_policy`, `test_jurisdiction_policy` |
| SE-09 | Audit and metrics | 1 | passed | `test_audit_event` |
| SE-10 | Documentation and runbooks | 2 | passed | `test_adrs_accepted`, `test_runbooks_exist` |

## Blockers
No blocking items.
