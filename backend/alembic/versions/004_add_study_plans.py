"""add study_plans and study_topics tables

Revision ID: 004
Revises: 003
Create Date: 2026-02-24
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ──
    op.execute(
        "CREATE TYPE study_plan_status AS ENUM ('generating', 'ready', 'failed')"
    )
    op.execute("CREATE TYPE topic_priority AS ENUM ('high', 'medium', 'low')")
    op.execute("CREATE TYPE topic_difficulty AS ENUM ('hard', 'medium', 'easy')")

    # ── study_plans table ──
    op.execute("""
        CREATE TABLE study_plans (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            space_id        UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
            title           VARCHAR(500) NOT NULL,
            exam_date       TIMESTAMPTZ,
            daily_hours     DOUBLE PRECISION NOT NULL DEFAULT 2.0,
            status          study_plan_status NOT NULL DEFAULT 'generating',
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TRIGGER trigger_study_plans_updated_at
        BEFORE UPDATE ON study_plans
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    # ── study_topics table ──
    op.execute("""
        CREATE TABLE study_topics (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            plan_id         UUID NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
            title           VARCHAR(500) NOT NULL,
            description     TEXT NOT NULL DEFAULT '',
            priority        topic_priority NOT NULL DEFAULT 'medium',
            difficulty      topic_difficulty NOT NULL DEFAULT 'medium',
            estimated_hours DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            source_pages    VARCHAR(500),
            order_index     INTEGER NOT NULL DEFAULT 0,
            completed       BOOLEAN NOT NULL DEFAULT FALSE,
            completed_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Indexes ──
    op.execute("CREATE INDEX idx_study_plans_space ON study_plans(space_id)")
    op.execute("CREATE INDEX idx_study_topics_plan ON study_topics(plan_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_study_topics_plan")
    op.execute("DROP INDEX IF EXISTS idx_study_plans_space")

    op.execute("DROP TABLE IF EXISTS study_topics")
    op.execute("DROP TRIGGER IF EXISTS trigger_study_plans_updated_at ON study_plans")
    op.execute("DROP TABLE IF EXISTS study_plans")

    op.execute("DROP TYPE IF EXISTS topic_difficulty")
    op.execute("DROP TYPE IF EXISTS topic_priority")
    op.execute("DROP TYPE IF EXISTS study_plan_status")
