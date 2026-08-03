"""Rule-based intent classifier for source hits."""

from __future__ import annotations

import re

from config.enums import IntentLabel
from services.source_engine.config import QueryLibraryLoader


def _score_terms(text: str, terms: list[str]) -> int:
    text_lower = text.lower()
    return sum(
        1 for term in terms if re.search(r"\b" + re.escape(term.lower()) + r"\b", text_lower)
    )


def classify_intent(
    title: str, body: str, query_family: str = "va_adjacent_jobs_v1"
) -> IntentLabel:
    """Classify a source hit into an intent label."""
    library = QueryLibraryLoader().get(query_family)
    text = f"{title} {body}"
    positive_titles = library.get("positive_titles", [])
    positive_phrases = library.get("positive_task_phrases", [])
    negative_terms = library.get("negative_terms", [])

    if _score_terms(text, negative_terms) > 0:
        if _score_terms(text, ["course", "training", "become a virtual assistant"]) > 0:
            return IntentLabel.JOB_SEEKER
        return IntentLabel.SELLER_PROMOTION

    title_score = _score_terms(text, positive_titles)
    phrase_score = _score_terms(text, positive_phrases)

    if title_score > 0 and phrase_score > 0:
        return IntentLabel.BUYER_REQUEST
    if title_score > 0:
        return IntentLabel.COMPANY_HIRING
    if phrase_score > 0:
        return IntentLabel.OPERATIONAL_PAIN
    if any(kw in text.lower() for kw in ["hiring", "we are hiring", "join our team"]):
        return IntentLabel.GROWTH_TRIGGER
    return IntentLabel.UNRESOLVED


def score_intent(label: IntentLabel) -> float:
    """Return a numeric intent strength for source hit scoring."""
    strengths: dict[IntentLabel, float] = {
        IntentLabel.BUYER_REQUEST: 1.0,
        IntentLabel.COMPANY_HIRING: 0.95,
        IntentLabel.OPERATIONAL_PAIN: 0.85,
        IntentLabel.GROWTH_TRIGGER: 0.5,
        IntentLabel.COMPANY_EXISTENCE_ONLY: 0.1,
        IntentLabel.SELLER_PROMOTION: 0.0,
        IntentLabel.JOB_SEEKER: 0.0,
        IntentLabel.GENERAL_DISCUSSION: 0.0,
        IntentLabel.UNRESOLVED: 0.0,
    }
    return strengths.get(label, 0.0)
