"""Tests for configuration validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from services.source_engine.config import SourceRegistryLoader

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_validate_configs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_configs.py"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "All configuration files valid" in result.stdout


def test_directory_sources_use_three_bounded_request_lanes() -> None:
    registry = SourceRegistryLoader().load()
    for source_key in ("finance_directory", "nz_finance_advisers"):
        rate_limit = registry[source_key].rate_limit
        assert rate_limit["requests_per_second"] == 3
        assert rate_limit["max_concurrency_per_host"] == 3
        assert rate_limit["max_total_concurrency"] == 3


def test_web_contact_shards_limit_total_domain_concurrency() -> None:
    registry = SourceRegistryLoader().load()
    for source_key in ("team_pages", "company_web"):
        assert registry[source_key].rate_limit["max_total_concurrency"] == 10


def test_openstreetmap_keeps_the_complete_business_tag_mapping() -> None:
    registry = SourceRegistryLoader().load()
    tags = registry["openstreetmap"].adapter_config["tags"]
    assert [(tag["key"], tag["value"]) for tag in tags] == [
        ("office", "estate_agent"),
        ("office", "property_manager"),
        ("office", "real_estate"),
        ("office", "accountant"),
        ("office", "lawyer"),
        ("office", "insurance"),
        ("office", "financial_advisor"),
        ("office", "bookkeeper"),
        ("office", "construction_company"),
        ("office", "administrative"),
        ("craft", "plumber"),
        ("craft", "electrician"),
        ("craft", "carpenter"),
        ("craft", "painter"),
        ("craft", "roofer"),
        ("craft", "hvac"),
    ]


def test_validate_source_registry_rejects_unknown_allowed_fields() -> None:
    """Unknown allowed_fields tokens such as names, titles, and social_profiles are rejected."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_configs", REPO_ROOT / "scripts" / "validate_configs.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    data = {
        "sources": {
            "bad_source": {
                "source_class": "manual_seed",
                "access_mode": "manual_import",
                "status": "enabled",
                "owner": "test",
                "terms_review_status": "approved",
                "allowed_fields": ["names", "titles", "social_profiles"],
            }
        }
    }
    errors = module.validate_source_registry(data, Path("test.yaml"))
    for token in ("names", "titles", "social_profiles"):
        assert any(f"unknown allowed_fields token '{token}'" in e for e in errors)


def test_validate_configs_rejects_non_mapping_entries() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_configs", REPO_ROOT / "scripts" / "validate_configs.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    source_errors = module.validate_source_registry(
        {"sources": {"bad_source": None}},
        Path("sources.yaml"),
    )
    query_errors = module.validate_query_library(
        {"families": {"bad_family": None}},
        Path("queries.yaml"),
    )

    assert source_errors == ["sources.yaml source 'bad_source' must be a mapping"]
    assert query_errors == ["queries.yaml family 'bad_family' must be a mapping"]
