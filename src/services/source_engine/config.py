"""Runtime source configuration objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = REPO_ROOT / "config" / "sources" / "source-registry.yaml"
DEFAULT_QUERY_LIBRARY = REPO_ROOT / "config" / "sources" / "query-library.yaml"


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
