from pydantic import HttpUrl

from domain.events.base import BaseEvent


class CrawlRequest(BaseEvent):
    """Request to crawl a single URL."""
    schema_version: str = "1.0.0"
    url: HttpUrl
    crawl_depth: int = 0
    browser_allowed: bool = False

__all__ = ["CrawlRequest"]
