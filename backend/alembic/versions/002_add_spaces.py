"""add spaces table and space_id to documents and quizzes

Revision ID: 002
Revises: 001
Create Date: 2026-02-23
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Spaces table ──
    op.execute("""
        CREATE TABLE spaces (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name            VARCHAR(255) NOT NULL,
            description     TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Auto-update updated_at on spaces
    op.execute("""
        CREATE TRIGGER trigger_spaces_updated_at
        BEFORE UPDATE ON spaces
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    # ── Add space_id FK to documents ──
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN space_id UUID REFERENCES spaces(id) ON DELETE CASCADE
    """)

    # ── Add space_id FK to quizzes ──
    op.execute("""
        ALTER TABLE quizzes
        ADD COLUMN space_id UUID REFERENCES spaces(id) ON DELETE CASCADE
    """)

    # ── Indexes ──
    op.execute("CREATE INDEX idx_spaces_updated ON spaces(updated_at DESC)")
    op.execute("CREATE INDEX idx_documents_space ON documents(space_id)")
    op.execute("CREATE INDEX idx_quizzes_space ON quizzes(space_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_quizzes_space")
    op.execute("DROP INDEX IF EXISTS idx_documents_space")
    op.execute("DROP INDEX IF EXISTS idx_spaces_updated")

    op.execute("ALTER TABLE quizzes DROP COLUMN IF EXISTS space_id")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS space_id")

    op.execute("DROP TRIGGER IF EXISTS trigger_spaces_updated_at ON spaces")
    op.execute("DROP TABLE IF EXISTS spaces")
