"""Tests for contract generation scripts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def test_openapi_export() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "openapi.json"
        result = _run("python", "scripts/export_openapi.py", "--output", str(path))
        assert result.returncode == 0
        schema = json.loads(path.read_text())
        assert schema.get("info", {}).get("title") == "VA Lead Intelligence API"


def test_json_schema_export() -> None:
    with TemporaryDirectory() as tmp:
        result = _run("python", "scripts/export_json_schemas.py", "--output-dir", tmp)
        assert result.returncode == 0
        files = list(Path(tmp).glob("*.schema.json"))
        assert len(files) > 0


def test_erd_render() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "erd.svg"
        result = _run("python", "scripts/render_erd.py", "--output", str(path), "--from-metadata")
        assert result.returncode == 0
        assert path.exists()
