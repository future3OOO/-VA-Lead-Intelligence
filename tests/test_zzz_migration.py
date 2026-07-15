"""Tests for Alembic migrations, run last because downgrade drops tables."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_migration_is_at_head() -> None:
    result = _alembic("current")
    assert "head" in result.stdout.lower()


def test_migration_file_exists() -> None:
    versions = list((REPO_ROOT / "migrations" / "versions").glob("*.py"))
    assert len(versions) > 0


def test_migration_downgrade() -> None:
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")
