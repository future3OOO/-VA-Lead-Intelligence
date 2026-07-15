"""Tests for documentation and governance artifacts."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_adrs_accepted() -> None:
    adr_dir = REPO_ROOT / "docs" / "adr"
    adrs = list(adr_dir.glob("ADR-*.md"))
    assert len(adrs) >= 1
    for path in adrs:
        assert "accepted" in path.read_text().lower(), f"{path} is not accepted"


def test_runbooks_exist() -> None:
    runbook_dir = REPO_ROOT / "docs" / "runbooks"
    required = [
        "incident-response.md",
        "rollback.md",
        "deployment.md",
        "crawler-operations.md",
        "scoring-tuning.md",
    ]
    for name in required:
        assert (runbook_dir / name).exists(), f"Missing runbook: {name}"
