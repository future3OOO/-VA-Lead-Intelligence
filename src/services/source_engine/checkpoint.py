"""Simple JSON checkpoint store for source adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CHECKPOINT_DIR = REPO_ROOT / "data" / "checkpoints"


class CheckpointStore:
    """File-backed checkpoint store."""

    def __init__(self, source_key: str, base_dir: Path | None = None) -> None:
        self.source_key = source_key
        self.base_dir = base_dir or DEFAULT_CHECKPOINT_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, workspace_id: UUID) -> Path:
        return self.base_dir / f"{self.source_key}_{workspace_id}.json"

    def load(self, workspace_id: UUID) -> dict[str, Any]:
        path = self._path(workspace_id)
        if not path.exists():
            return {}
        try:
            return cast(dict[str, Any], json.loads(path.read_text()))
        except json.JSONDecodeError:
            return {}

    def save(self, workspace_id: UUID, data: dict[str, Any]) -> None:
        path = self._path(workspace_id)
        existing = self.load(workspace_id)
        existing.update(data)
        path.write_text(json.dumps(existing, indent=2, default=str) + "\n")
