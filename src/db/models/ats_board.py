import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AtsBoard(Base):
    """Parsed ATS board.."""
    __tablename__ = "ats_board"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workspace.id'), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('company.id'), index=True)
    provider: Mapped[str] = mapped_column(String(255))
    board_url: Mapped[str] = mapped_column(String(2048))
    board_token: Mapped[str] = mapped_column(String(255))
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

__all__ = ["AtsBoard"]
