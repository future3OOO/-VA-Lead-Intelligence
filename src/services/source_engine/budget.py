"""Cost budget enforcement for source adapters."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class Budget:
    """Tracks spend against a per-source cap."""

    currency: str = "USD"
    max_spend: Decimal = Decimal("0")
    spent: Decimal = Decimal("0")

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> Budget:
        cfg = config or {}
        return cls(
            currency=cfg.get("currency", "USD"),
            max_spend=Decimal(str(cfg.get("max_spend", 0))),
            spent=Decimal(str(cfg.get("spent", 0))),
        )

    def remaining(self) -> Decimal:
        return self.max_spend - self.spent

    def can_spend(self, amount: Decimal) -> bool:
        if self.max_spend <= 0:
            return True
        return (self.spent + amount) <= self.max_spend

    def spend(self, amount: Decimal, units: int = 1) -> None:
        self.spent += amount * units
