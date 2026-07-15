from pydantic import HttpUrl

from config.enums import SourceType
from domain.events.base import BaseEvent


class AtsBoard(BaseEvent):
    """Parsed ATS board snapshot."""
    schema_version: str = "1.0.0"
    board_url: HttpUrl
    provider: SourceType
    board_token: str

__all__ = ["AtsBoard"]
