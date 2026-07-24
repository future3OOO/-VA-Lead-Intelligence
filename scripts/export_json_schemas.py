#!/usr/bin/env python3
"""Export JSON Schemas for all Pydantic event/domain models."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from pydantic import BaseModel  # noqa: E402


def to_snake(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def deep_sort(obj: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    if isinstance(obj, dict):
        return {k: deep_sort(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [deep_sort(item) if isinstance(item, (dict, list)) else item for item in obj]
    return obj


def set_additional_properties_false(schema: dict[str, Any]) -> None:
    if isinstance(schema, dict):
        if (
            schema.get("type") == "object"
            and "properties" in schema
            and "additionalProperties" not in schema
        ):
            schema["additionalProperties"] = False
        for value in schema.values():
            set_additional_properties_false(value)
    elif isinstance(schema, list):
        for item in schema:
            set_additional_properties_false(item)


def export_model(cls: type[BaseModel], output_dir: Path) -> Path:
    schema = cls.model_json_schema(by_alias=False, ref_template="#/$defs/{model}")
    set_additional_properties_false(schema)

    version = "1.0.0"
    if "properties" in schema and "schema_version" in schema["properties"]:
        default = schema["properties"]["schema_version"].get("default")
        if default:
            version = str(default)

    name = to_snake(cls.__name__)
    schema["$id"] = f"https://schemas.va-lead-intelligence/{name}-v{version}.schema.json"
    schema["version"] = version

    output_path = output_dir / f"{name}.schema.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(deep_sort(schema), indent=2, ensure_ascii=False) + "\n")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    import domain.events
    import domain.models

    count = 0
    for module in (domain.events, domain.models):
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            cls = getattr(module, attr_name)
            if isinstance(cls, type) and issubclass(cls, BaseModel) and cls is not BaseModel:
                export_model(cls, args.output_dir)
                count += 1

    print(f"Exported {count} JSON schemas to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
