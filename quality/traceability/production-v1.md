# DOD Traceability Report — VA Lead Intelligence

| Requirement | Title | Tests | Status | Evidence |
|-------------|-------|-------|--------|----------|
| RQ-001 | Multi-tenant workspace authorization | 3 | passed | `test_unauthorized_request`, `test_create_company_requires_workspace`, `test_workspace_isolation` |
| RQ-002 | Capability-driven lead scoring | 4 | passed | `test_high_fit_passes`, `test_low_fit_fails`, `test_score_determinism`, `test_benchmark` |
| RQ-003 | Source and jurisdiction compliance | 2 | passed | `test_source_policy`, `test_jurisdiction_policy` |
| RQ-004 | Event sourcing and audit trail | 1 | passed | `test_audit_event` |
| RQ-005 | Automated contract generation | 3 | passed | `test_openapi_export`, `test_json_schema_export`, `test_erd_render` |
| RQ-006 | Database migrations are versioned and testable | 3 | passed | `test_migration_is_at_head`, `test_migration_file_exists`, `test_migration_downgrade` |
| RQ-007 | Infrastructure as code | 2 | passed | `test_terraform_validate`, `test_env_catalogue` |
| RQ-008 | Operational runbooks and ADRs are current | 2 | passed | `test_adrs_accepted`, `test_runbooks_exist` |

## Blockers
No blocking items.
