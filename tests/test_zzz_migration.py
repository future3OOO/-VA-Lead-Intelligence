"""Tests for Alembic migrations, run last because downgrade drops tables."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_migration_is_at_head() -> None:
    result = subprocess.run(
        ["alembic", "current"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "head" in result.stdout.lower()


def test_migration_file_exists() -> None:
    versions = list((REPO_ROOT / "migrations" / "versions").glob("*.py"))
    assert len(versions) > 0


def test_migration_downgrade() -> None:
    subprocess.run(
        ["alembic", "downgrade", "base"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
