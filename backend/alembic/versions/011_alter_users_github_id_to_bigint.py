"""alter users.github_id to bigint

Revision ID: 011
Revises: 010
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN github_id TYPE BIGINT")


def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN github_id TYPE INTEGER")
