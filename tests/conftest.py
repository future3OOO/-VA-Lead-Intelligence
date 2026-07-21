"""Shared test configuration and fixtures."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg2
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_DATABASE_NAME = "va_lead_intelligence_test"

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = (
    f"postgresql+asyncpg://postgres:postgres@localhost:5432/{TEST_DATABASE_NAME}"
)
# The manual_seed adapter sandboxes files under MANUAL_SEED_DIR. In tests the
# existing temp-file fixtures live under the system temp directory.
os.environ["MANUAL_SEED_DIR"] = tempfile.gettempdir()


def _create_test_db() -> None:
    base_url = "postgresql://postgres:postgres@localhost:5432/postgres"
    try:
        conn = psycopg2.connect(base_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME}")
        cur.execute(f"CREATE DATABASE {TEST_DATABASE_NAME}")
        cur.close()
        conn.close()
    except psycopg2.OperationalError:
        pass


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> None:
    _create_test_db()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
