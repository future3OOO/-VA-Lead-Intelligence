import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class PageSnapshot(Base):
    """PageSnapshot."""
    __tablename__ = "page_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workspace.id'), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    snapshot_path: Mapped[str] = mapped_column(String(255))
    etag: Mapped[str] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

__all__ = ["PageSnapshot"]
