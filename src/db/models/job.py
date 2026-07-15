import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Job(Base):
    """Job posting.."""
    __tablename__ = "job"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workspace.id'), index=True)
    ats_board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('ats_board.id'), index=True)
    external_job_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255))
    description_text: Mapped[str] = mapped_column(Text)
    remote_allowed: Mapped[bool] = mapped_column(Boolean)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

__all__ = ["Job"]
