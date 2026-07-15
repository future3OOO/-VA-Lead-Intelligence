#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to a JSON file."""
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def deep_sort(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {k: deep_sort(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [deep_sort(item) for item in obj]
    return obj


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    import sys
    sys.path.insert(0, str(REPO_ROOT / "src"))

    from api.app import app  # noqa: E402

    schema = app.openapi()
    sorted_schema = deep_sort(schema)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sorted_schema, indent=2, ensure_ascii=False) + "\n")
    print(f"Exported OpenAPI schema to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
