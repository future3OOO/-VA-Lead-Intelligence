"""Make source company identifiers unique within a workspace.

Revision ID: a6f9d8c7b2e1
Revises: 2dee9c0407d9
Create Date: 2026-07-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a6f9d8c7b2e1"
down_revision: Union[str, Sequence[str], None] = "2dee9c0407d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deduplicate and enforce stable source identity."""
    op.execute(
        """
        DELETE FROM company_identifier duplicate
        USING company_identifier retained
        WHERE duplicate.workspace_id = retained.workspace_id
          AND duplicate.source = retained.source
          AND duplicate.external_id = retained.external_id
          AND duplicate.id > retained.id
        """
    )
    op.create_unique_constraint(
        "uq_company_identifier_workspace_source_external",
        "company_identifier",
        ["workspace_id", "source", "external_id"],
    )


def downgrade() -> None:
    """Remove the source identity constraint."""
    op.drop_constraint(
        "uq_company_identifier_workspace_source_external",
        "company_identifier",
        type_="unique",
    )
