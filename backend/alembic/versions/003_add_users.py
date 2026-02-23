"""add users table and user_id to spaces

Revision ID: 003
Revises: 002
Create Date: 2026-02-23
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Users table ──
    op.execute("""
        CREATE TABLE users (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            github_id       INTEGER NOT NULL UNIQUE,
            username        VARCHAR(255) NOT NULL,
            email           VARCHAR(500),
            avatar_url      VARCHAR(1000),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Auto-update updated_at on users
    op.execute("""
        CREATE TRIGGER trigger_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    # ── Add user_id FK to spaces ──
    op.execute("""
        ALTER TABLE spaces
        ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE CASCADE
    """)

    # ── Indexes ──
    op.execute("CREATE INDEX idx_users_github_id ON users(github_id)")
    op.execute("CREATE INDEX idx_spaces_user ON spaces(user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_spaces_user")
    op.execute("DROP INDEX IF EXISTS idx_users_github_id")

    op.execute("ALTER TABLE spaces DROP COLUMN IF EXISTS user_id")

    op.execute("DROP TRIGGER IF EXISTS trigger_users_updated_at ON users")
    op.execute("DROP TABLE IF EXISTS users")
