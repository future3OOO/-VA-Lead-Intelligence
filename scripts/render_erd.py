#!/usr/bin/env python3
"""Render an ERD from the SQLAlchemy metadata and write it as an SVG."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from eralchemy2 import render_er  # noqa: E402

import db.models  # noqa: E402, F401
from config.settings import Settings  # noqa: E402
from db.base import Base  # noqa: E402


def _stabilize_edge_ids(svg_path: Path) -> None:
    """Reassign edge IDs in an SVG deterministically by edge title."""
    text = svg_path.read_text()
    ns_match = re.search(r'xmlns="([^"]+)"', text)
    namespace = ns_match.group(1) if ns_match else "http://www.w3.org/2000/svg"
    if not ns_match:
        return

    root = ET.fromstring(text)
    ns = {"svg": namespace}
    edges: list[tuple[ET.Element, str]] = []
    for g in root.iter(f"{{{namespace}}}g"):
        if g.get("class") == "edge":
            title = g.find("svg:title", ns)
            if title is not None and title.text:
                edges.append((g, title.text))

    edges.sort(key=lambda item: item[1])
    for i, (g, _) in enumerate(edges):
        g.set("id", f"edge{i}")

    svg_path.write_bytes(ET.tostring(root, encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--from-metadata", action="store_true", help="Render from metadata without a live database."
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    source: Any = (
        Base.metadata
        if args.from_metadata
        else Settings().database_url.replace("+asyncpg", "+psycopg2")
    )

    render_er(source, str(args.output))  # type: ignore[no-untyped-call]
    _stabilize_edge_ids(args.output)
    print(f"Rendered ERD to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
