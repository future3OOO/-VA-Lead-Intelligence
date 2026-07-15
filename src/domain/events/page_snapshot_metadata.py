from datetime import datetime

from pydantic import HttpUrl

from domain.events.base import BaseEvent


class PageSnapshotMetadata(BaseEvent):
    """Metadata for a stored page snapshot."""
    schema_version: str = "1.0.0"
    url: HttpUrl
    snapshot_path: str
    etag: str
    fetched_at: datetime

__all__ = ["PageSnapshotMetadata"]
