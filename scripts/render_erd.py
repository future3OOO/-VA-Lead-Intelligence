#!/usr/bin/env python3
"""Render an ERD from the SQLAlchemy metadata and write it as an SVG."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from eralchemy2 import render_er  # noqa: E402

from config.settings import Settings  # noqa: E402
import db.models  # noqa: E402, F401
from db.base import Base  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--from-metadata", action="store_true", help="Render from metadata without a live database.")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    source: Any = Base.metadata if args.from_metadata else Settings().database_url.replace("+asyncpg", "+psycopg2")

    render_er(source, str(args.output))  # type: ignore[no-untyped-call]
    print(f"Rendered ERD to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
