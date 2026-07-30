"""Tests for configuration validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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


def test_validate_source_registry_rejects_unknown_allowed_fields() -> None:
    """Unknown allowed_fields tokens such as names, titles, and social_profiles are rejected."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_configs", REPO_ROOT / "scripts" / "validate_configs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

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
