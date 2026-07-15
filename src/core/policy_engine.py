"""Source and jurisdiction policy engine."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_POLICY = REPO_ROOT / "config" / "source-policy" / "default.yaml"
JURISDICTION_POLICY = REPO_ROOT / "config" / "jurisdiction-policy" / "default.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def evaluate_source(source_id: str, path: Path | None = None) -> dict[str, Any]:
    data = load_yaml(path or SOURCE_POLICY)
    default = {"allowed": False, "reason": "source_not_configured"}
    for source in data.get("sources", []):
        if source["id"] == source_id:
            if source.get("allowed"):
                return {"allowed": True, "ttl_hours": source.get("rate_limit_daily", data.get("default_ttl_hours", 720))}
            return {"allowed": False, "reason": "source_blocked"}
    prohibited = {p["id"] for p in data.get("prohibited_sources", [])}
    if source_id in prohibited:
        return {"allowed": False, "reason": "prohibited_source"}
    return default


def evaluate_jurisdiction(country_code: str, path: Path | None = None) -> dict[str, Any]:
    data = load_yaml(path or JURISDICTION_POLICY)
    rules = data.get("rules", [])
    for rule in rules:
        if rule.get("country_code") == country_code:
            return {
                "allowed": rule.get("status") == "allowed",
                "conditional": rule.get("status") == "conditional",
                "reason": rule.get("reason", rule.get("status")),
                "retention_days": data.get("retention_days"),
                "rights": rule.get("data_subject_rights", []),
            }
    default_status = data.get("default_status", "conditional")
    return {
        "allowed": default_status == "allowed",
        "conditional": default_status == "conditional",
        "reason": "default_policy",
        "retention_days": data.get("retention_days"),
        "rights": [],
    }
