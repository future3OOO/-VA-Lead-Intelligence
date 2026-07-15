"""Abstract adapter interface for lead-generation sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SourceAdapter(ABC):
    """Base class for all source adapters."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique source identifier."""
        ...

    @abstractmethod
    async def fetch(self, workspace_id: str, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch raw records for the given workspace and source config."""
        ...

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw record into a source_event payload."""
        ...


class HttpSourceAdapter(SourceAdapter):
    """Generic HTTP source adapter with rate limiting hooks."""

    def __init__(self, source_id: str, base_url: str) -> None:
        self._source_id = source_id
        self._base_url = base_url

    @property
    def source_id(self) -> str:
        return self._source_id

    async def fetch(self, workspace_id: str, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Placeholder fetch; real implementation performs HTTP GET with retries."""
        return []

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_id": self._source_id,
            "source_type": "http",
            "raw_payload": raw,
        }
