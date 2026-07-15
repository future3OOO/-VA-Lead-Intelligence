import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CompanyRelationship(Base):
    """CompanyRelationship."""
    __tablename__ = "company_relationship"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workspace.id'), index=True)
    parent_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('company.id'), index=True)
    child_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('company.id'), index=True)
    relationship_type: Mapped[str] = mapped_column(String(255))

__all__ = ["CompanyRelationship"]
