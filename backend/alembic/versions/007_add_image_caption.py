"""add caption column to document_images

Revision ID: 007
Revises: 006
Create Date: 2026-03-04
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE document_images ADD COLUMN caption TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE document_images DROP COLUMN IF EXISTS caption")
