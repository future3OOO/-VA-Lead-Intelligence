"""Source-level hit scorer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.enums import IntentLabel
from services.source_engine.classifier import score_intent


def _freshness(published_at: datetime | None) -> float:
    if not published_at:
        return 0.5
    age_days = (datetime.now(timezone.utc) - published_at).days
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.75
    if age_days <= 90:
        return 0.5
    return 0.25


def _evidence_quality(body_excerpt: str, contact_routes_raw: list[Any]) -> float:
    score = 0.0
    if body_excerpt:
        score += min(0.5, len(body_excerpt) / 2000)
    if contact_routes_raw:
        score += min(0.5, len(contact_routes_raw) * 0.25)
    return min(1.0, score)


def _contactability_hint(contact_routes_raw: list[Any]) -> float:
    return 1.0 if contact_routes_raw else 0.0


def _to_intent_label(value: Any) -> IntentLabel:
    if isinstance(value, IntentLabel):
        return value
    try:
        return IntentLabel(str(value))
    except ValueError:
        return IntentLabel.UNRESOLVED


def score_source_hit(source_hit: dict[str, Any]) -> float:
    """Compute source hit priority using the spec formula."""
    intent_strength = score_intent(_to_intent_label(source_hit.get("intent_label")))
    company_resolvability = (
        1.0 if (source_hit.get("company_domain_raw") or source_hit.get("company_name_raw")) else 0.0
    )
    freshness = _freshness(source_hit.get("published_at"))
    evidence_quality = _evidence_quality(
        source_hit.get("body_excerpt", ""), source_hit.get("contact_routes_raw", [])
    )
    contactability = _contactability_hint(source_hit.get("contact_routes_raw", []))
    source_stability = 1.0

    return round(
        0.35 * intent_strength
        + 0.20 * company_resolvability
        + 0.15 * freshness
        + 0.15 * evidence_quality
        + 0.10 * contactability
        + 0.05 * source_stability,
        4,
    )
