"""Tests for infrastructure as code."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_terraform_validate() -> None:
    tf_dir = REPO_ROOT / "infra" / "terraform"
    fmt = subprocess.run(
        ["terraform", "fmt", "-check", "-recursive"],
        cwd=tf_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    assert fmt.returncode == 0, fmt.stdout + fmt.stderr

    init = subprocess.run(
        ["terraform", "init", "-backend=false"],
        cwd=tf_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    assert init.returncode == 0, init.stdout + init.stderr

    validate = subprocess.run(
        ["terraform", "validate"],
        cwd=tf_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr


def test_env_catalogue() -> None:
    with TemporaryDirectory() as tmp:
        output = Path(tmp) / "ENVIRONMENT_CATALOGUE.md"
        result = subprocess.run(
            [sys.executable, "scripts/export_env_catalogue.py", "--output", str(output)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert output.exists()
