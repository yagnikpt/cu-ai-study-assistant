"""add ingestion_progress and image_ingestion_progress columns to documents

Revision ID: 009
Revises: 008
Create Date: 2026-03-06
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum types
    op.execute(
        "CREATE TYPE ingestion_progress AS ENUM "
        "('uploading', 'parsing', 'chunking', 'embedding', 'storing', 'done')"
    )
    op.execute(
        "CREATE TYPE image_ingestion_progress AS ENUM "
        "('pending', 'uploading', 'embedding', 'storing', 'done', 'skipped')"
    )

    # Add nullable columns to documents
    op.execute("ALTER TABLE documents ADD COLUMN progress ingestion_progress")
    op.execute(
        "ALTER TABLE documents ADD COLUMN images_progress image_ingestion_progress"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS images_progress")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS progress")
    op.execute("DROP TYPE IF EXISTS image_ingestion_progress")
    op.execute("DROP TYPE IF EXISTS ingestion_progress")
