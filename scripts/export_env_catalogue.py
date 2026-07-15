#!/usr/bin/env python3
"""Generate an environment variable catalogue from Settings and Terraform."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config.settings import Settings  # noqa: E402


def parse_settings() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, field in Settings.model_fields.items():
        default = field.default
        rows.append(
            {
                "name": name.upper(),
                "description": field.description or "",
                "default": default if not isinstance(default, type) else "",
                "required": field.is_required(),
            }
        )
    return rows


def parse_terraform_vars() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tf_dir = REPO_ROOT / "infra" / "terraform"
    if not tf_dir.exists():
        return rows
    for path in sorted(tf_dir.rglob("*.tf")):
        text = path.read_text()
        for match in re.finditer(r'variable\s+"([^"]+)"\s*\{([^}]*)\}', text, re.DOTALL):
            name = match.group(1)
            body = match.group(2)
            desc_match = re.search(r'description\s*=\s*"([^"]*)"', body)
            default_match = re.search(r"default\s*=\s*([^\n]+)", body)
            rows.append(
                {
                    "name": f"TF_VAR_{name}",
                    "description": desc_match.group(1) if desc_match else "",
                    "default": default_match.group(1).strip() if default_match else "",
                    "required": "default" not in body,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    rows = parse_settings() + parse_terraform_vars()

    lines = ["# Environment Variable Catalogue", ""]
    lines.append("| Variable | Required | Default | Description |")
    lines.append("|----------|----------|---------|-------------|")
    for row in rows:
        default = row["default"] if row["default"] is not None else ""
        default_str = str(default) if not isinstance(default, type) else ""
        lines.append(
            f"| `{row['name']}` | {row['required']} | `{default_str}` | {row['description']} |"
        )

    args.output.write_text("\n".join(lines) + "\n")
    print(f"Exported environment catalogue to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
