#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema as a deterministic JSON file."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from api.app import app  # noqa: E402


def deep_sort(obj: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    if isinstance(obj, dict):
        return {k: deep_sort(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [deep_sort(item) if isinstance(item, (dict, list)) else item for item in obj]
    return obj


def build_sha() -> str:
    sha = os.environ.get("BUILD_SHA", "")
    if not sha:
        try:
            sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            sha = "unknown"
    return sha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    schema = app.openapi()
    schema.setdefault("info", {})
    schema["info"]["x-build-sha"] = build_sha()
    schema["info"]["x-generated-at"] = subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip()

    sorted_schema = deep_sort(schema)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sorted_schema, indent=2, ensure_ascii=False) + "\n")
    print(f"Exported OpenAPI schema to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
