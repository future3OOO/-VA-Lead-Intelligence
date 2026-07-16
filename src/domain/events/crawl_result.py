from typing import Any

from pydantic import Field

from config.enums import CrawlStatus
from domain.events.base import BaseEvent


class CrawlResult(BaseEvent):
    """Result of a crawl."""

    schema_version: str = "1.0.0"
    crawl_request: dict[str, Any]
    status: CrawlStatus
    content_text: str
    links: list[str] = Field(default_factory=list)


__all__ = ["CrawlResult"]
