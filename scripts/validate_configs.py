#!/usr/bin/env python3
"""Validate business YAML configuration files."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"

# Allow importing the source-engine config module for the canonical token list.
sys.path.insert(0, str(REPO_ROOT / "src"))
from services.source_engine.config import ALLOWED_FIELD_MAP  # noqa: E402


def validate_yaml(path: Path) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], yaml.safe_load(path.read_text()) or {})
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc


def validate_taxonomy(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    if "capabilities" not in data:
        errors.append(f"{path} missing 'capabilities' key")
    for i, cap in enumerate(data.get("capabilities", [])):
        for key in ("id", "name", "category"):
            if key not in cap:
                errors.append(f"{path} capability[{i}] missing {key}")
    return errors


def validate_scorecard(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    for key in ("version", "scorecard_id", "min_score", "dimensions"):
        if key not in data:
            errors.append(f"{path} missing {key}")
    for i, dim in enumerate(data.get("dimensions", [])):
        for key in ("id", "weight"):
            if key not in dim:
                errors.append(f"{path} dimension[{i}] missing {key}")
    return errors


def validate_policy(data: dict[str, Any], path: Path, required_root: str) -> list[str]:
    errors: list[str] = []
    if required_root not in data:
        errors.append(f"{path} missing '{required_root}' key")
    if "version" not in data:
        errors.append(f"{path} missing version")
    if "approved_at" not in data:
        errors.append(f"{path} missing approved_at")
    else:
        try:
            approved = datetime.fromisoformat(str(data["approved_at"])).replace(tzinfo=timezone.utc)
            if approved > datetime.now(timezone.utc):
                errors.append(f"{path} approved_at is in the future")
        except ValueError as exc:
            errors.append(f"{path} invalid approved_at: {exc}")
    return errors


def validate_source_registry(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    sources = data.get("sources", {})
    if not isinstance(sources, dict):
        errors.append(f"{path} 'sources' must be a mapping")
        return errors
    for key, cfg in sources.items():
        for field in ("source_class", "access_mode", "status", "owner", "terms_review_status"):
            if not cfg.get(field):
                errors.append(f"{path} source '{key}' missing {field}")
        for token in cfg.get("allowed_fields", []):
            if token not in ALLOWED_FIELD_MAP:
                errors.append(f"{path} source '{key}' has unknown allowed_fields token '{token}'")
    return errors


def validate_query_library(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    families = data.get("families", {})
    if not isinstance(families, dict):
        errors.append(f"{path} 'families' must be a mapping")
        return errors
    for key, family in families.items():
        for field in ("positive_titles", "positive_task_phrases", "negative_terms"):
            if not isinstance(family.get(field), list):
                errors.append(f"{path} family '{key}' missing or invalid {field}")
    return errors


def validate_source_policy(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    if "version" not in data:
        errors.append(f"{path} missing version")
    if "allowed_access_modes" not in data:
        errors.append(f"{path} missing allowed_access_modes")
    if "retention" not in data:
        errors.append(f"{path} missing retention")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    args = parser.parse_args()

    errors: list[str] = []
    validators: dict[str, Callable[[dict[str, Any], Path], list[str]]] = {
        "capability-taxonomy/capabilities.yaml": validate_taxonomy,
        "scorecards/default.yaml": validate_scorecard,
        "source-policy/default.yaml": lambda data, p: validate_policy(data, p, "sources"),
        "jurisdiction-policy/default.yaml": lambda data, p: validate_policy(data, p, "rules"),
        "sources/source-registry.yaml": validate_source_registry,
        "sources/query-library.yaml": validate_query_library,
        "sources/source-policies/default.yaml": validate_source_policy,
    }

    for rel_path, validator in validators.items():
        path = args.config_dir / rel_path
        if not path.exists():
            errors.append(f"Required config missing: {path}")
            continue
        try:
            data = validate_yaml(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validator(data, path))

    if errors:
        print("\n".join(f"  - {e}" for e in errors))
        return 1

    print("All configuration files valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
