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
