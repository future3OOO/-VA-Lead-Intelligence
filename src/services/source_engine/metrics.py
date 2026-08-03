"""In-memory source adapter metrics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceMetrics:
    """Collects per-source metrics during a run."""

    source_key: str
    counters: Counter[str] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)

    def record_hits(self, count: int) -> None:
        self.counters["source_hits_total"] += count

    def record_qualified(self, count: int) -> None:
        self.counters["source_hits_qualified_total"] += count

    def record_duplicate(self, count: int = 1) -> None:
        self.counters["source_hits_duplicate_total"] += count

    def record_error(self, category: str = "generic") -> None:
        self.errors[f"source_adapter_error_rate_{category}"] += 1

    def record_resolution(self, success: bool) -> None:
        key = (
            "source_company_resolution_rate" if success else "source_company_resolution_error_rate"
        )
        self.counters[key] += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_key": self.source_key,
            "counters": dict(self.counters),
            "errors": dict(self.errors),
        }
