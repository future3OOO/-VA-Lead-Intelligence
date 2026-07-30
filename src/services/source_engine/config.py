"""Runtime source configuration objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = REPO_ROOT / "config" / "sources" / "source-registry.yaml"
DEFAULT_QUERY_LIBRARY = REPO_ROOT / "config" / "sources" / "query-library.yaml"
DEFAULT_SOURCE_POLICY = REPO_ROOT / "config" / "sources" / "source-policies" / "default.yaml"

# Map registry allowed_fields tokens to SourceHit model field names.
ALLOWED_FIELD_MAP: dict[str, str] = {
    "company_name": "company_name_raw",
    "company_domain": "company_domain_raw",
    "title": "title",
    "body": "body_excerpt",
    "description": "body_excerpt",
    "location": "location_raw",
    "workplace_type": "workplace_type",
    "contact_routes": "contact_routes_raw",
    "source_url": "source_url",
    "source_native_id": "source_native_id",
    "raw_snapshot_uri": "raw_snapshot_uri",
    "access_policy_version": "access_policy_version",
    "intent_label": "intent_label",
}


@dataclass
class SourcePolicy:
    """Source access and jurisdiction policy gate."""

    allowed_access_modes: set[str]
    prohibited_access_modes: set[str]
    max_raw_retention_days: int
    max_normalized_retention_days: int
    jurisdiction_requirements: list[str]
    contact_route_after_qualification_only: bool

    @classmethod
    def load(cls, path: Path = DEFAULT_SOURCE_POLICY) -> SourcePolicy:
        data = cast(dict[str, Any], yaml.safe_load(path.read_text()) or {})
        retention = data.get("retention", {})
        return cls(
            allowed_access_modes=set(data.get("allowed_access_modes", [])),
            prohibited_access_modes=set(data.get("prohibited_access_modes", [])),
            max_raw_retention_days=int(retention.get("raw_snapshot_days", 90)),
            max_normalized_retention_days=int(retention.get("normalized_record_days", 730)),
            jurisdiction_requirements=list(data.get("jurisdiction_requirements", [])),
            contact_route_after_qualification_only=bool(
                retention.get("contact_route_after_qualification_only", True)
            ),
        )

    def validate(self, config: SourceConfig) -> tuple[bool, str]:
        """Return (ok, reason) for the configured source."""
        if config.access_mode in self.prohibited_access_modes:
            return False, f"access_mode '{config.access_mode}' is prohibited by source policy"
        if self.allowed_access_modes and config.access_mode not in self.allowed_access_modes:
            return False, f"access_mode '{config.access_mode}' is not allowed by source policy"
        if config.terms_review_status != "approved":
            return False, f"terms_review_status '{config.terms_review_status}' is not approved"
        if config.raw_retention_days > self.max_raw_retention_days:
            return False, "raw_retention_days exceeds source policy maximum"
        if config.normalized_retention_days > self.max_normalized_retention_days:
            return False, "normalized_retention_days exceeds source policy maximum"
        if not self.jurisdiction_requirements:
            return False, "no jurisdiction requirements configured in source policy"
        return True, ""


@dataclass
class SourceConfig:
    """Loaded source registry entry plus runtime overrides."""

    source_key: str
    source_class: str
    access_mode: str
    status: str
    owner: str
    terms_review_status: str
    terms_reviewed_at: str | None
    allowed_outputs: list[str] = field(default_factory=list)
    allowed_fields: list[str] = field(default_factory=list)
    raw_retention_days: int = 90
    normalized_retention_days: int = 730
    rate_limit: dict[str, Any] = field(default_factory=dict)
    kill_switch: str = ""
    adapter_config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, source_key: str, data: dict[str, Any]) -> SourceConfig:
        return cls(
            source_key=source_key,
            source_class=data.get("source_class", ""),
            access_mode=data.get("access_mode", ""),
            status=data.get("status", "enabled"),
            owner=data.get("owner", ""),
            terms_review_status=data.get("terms_review_status", ""),
            terms_reviewed_at=data.get("terms_reviewed_at"),
            allowed_outputs=data.get("allowed_outputs", []),
            allowed_fields=data.get("allowed_fields", []),
            raw_retention_days=int(data.get("raw_retention_days", 90)),
            normalized_retention_days=int(data.get("normalized_retention_days", 730)),
            rate_limit=data.get("rate_limit", {}),
            kill_switch=data.get("kill_switch", ""),
            adapter_config=data.get("adapter_config", {}),
        )


class SourceRegistryLoader:
    """Load the source registry from YAML."""

    def __init__(self, path: Path = DEFAULT_REGISTRY) -> None:
        self.path = path

    def load(self) -> dict[str, SourceConfig]:
        data = cast(dict[str, Any], yaml.safe_load(self.path.read_text()) or {})
        entries = cast(dict[str, Any], data.get("sources", {}))
        return {key: SourceConfig.from_dict(key, value) for key, value in entries.items()}

    def get(self, source_key: str) -> SourceConfig | None:
        return self.load().get(source_key)


class QueryLibraryLoader:
    """Load the query library from YAML."""

    def __init__(self, path: Path = DEFAULT_QUERY_LIBRARY) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        return cast(dict[str, Any], yaml.safe_load(self.path.read_text()) or {})

    def get(self, family_key: str) -> dict[str, Any]:
        families = cast(dict[str, Any], self.load().get("families", {}))
        return cast(dict[str, Any], families.get(family_key, {}))
