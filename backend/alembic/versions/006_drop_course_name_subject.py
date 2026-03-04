"""drop course_name and subject columns from documents table

Revision ID: 006
Revises: 005
Create Date: 2026-03-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("idx_documents_course", table_name="documents")
    op.drop_column("documents", "course_name")
    op.drop_column("documents", "subject")


def downgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("subject", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("course_name", sa.String(length=200), nullable=True),
    )
    op.create_index("idx_documents_course", "documents", ["course_name"])
