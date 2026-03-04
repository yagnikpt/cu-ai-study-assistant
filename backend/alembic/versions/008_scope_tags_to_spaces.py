"""scope tags to spaces — add space_id FK, composite unique constraint

Revision ID: 008
Revises: 007
Create Date: 2026-03-04
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable space_id column
    op.execute(
        "ALTER TABLE tags ADD COLUMN space_id UUID "
        "REFERENCES spaces(id) ON DELETE CASCADE"
    )

    # 2. Backfill: assign orphan tags to the space of their first associated document.
    #    Tags with no documents stay NULL and will be cleaned up next.
    op.execute("""
        UPDATE tags
        SET space_id = sub.space_id
        FROM (
            SELECT DISTINCT ON (dt.tag_id)
                dt.tag_id,
                d.space_id
            FROM document_tags dt
            JOIN documents d ON d.id = dt.document_id
            WHERE d.space_id IS NOT NULL
            ORDER BY dt.tag_id
        ) sub
        WHERE tags.id = sub.tag_id
    """)

    # 3. Delete tags that still have no space (orphans not linked to any document,
    #    or linked only to documents with no space).
    op.execute("DELETE FROM tags WHERE space_id IS NULL")

    # 4. Make space_id NOT NULL now that all rows have a value
    op.execute("ALTER TABLE tags ALTER COLUMN space_id SET NOT NULL")

    # 5. Drop the old global unique constraint on name
    op.execute("ALTER TABLE tags DROP CONSTRAINT IF EXISTS tags_name_key")

    # 6. Add composite unique: (name, space_id) — same name allowed in different spaces
    op.execute(
        "ALTER TABLE tags ADD CONSTRAINT uq_tags_name_space UNIQUE (name, space_id)"
    )

    # 7. Index for faster lookups by space
    op.execute("CREATE INDEX IF NOT EXISTS ix_tags_space_id ON tags (space_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tags_space_id")
    op.execute("ALTER TABLE tags DROP CONSTRAINT IF EXISTS uq_tags_name_space")
    op.execute("ALTER TABLE tags ADD CONSTRAINT tags_name_key UNIQUE (name)")
    op.execute("ALTER TABLE tags DROP COLUMN IF EXISTS space_id")
