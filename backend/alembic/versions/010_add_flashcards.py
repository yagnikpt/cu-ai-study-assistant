"""add flashcard_decks, flashcards, and flashcard_reviews tables

Revision ID: 010
Revises: 009
Create Date: 2026-03-06
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute(
        "CREATE TYPE flashcard_type AS ENUM ('term_definition', 'question_answer')"
    )
    op.execute("CREATE TYPE review_rating AS ENUM ('again', 'hard', 'good', 'easy')")

    # Create flashcard_decks table
    op.execute("""
        CREATE TABLE flashcard_decks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(500) NOT NULL,
            document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
            space_id UUID REFERENCES spaces(id) ON DELETE CASCADE,
            topic VARCHAR(500),
            card_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Create flashcards table
    op.execute("""
        CREATE TABLE flashcards (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deck_id UUID NOT NULL REFERENCES flashcard_decks(id) ON DELETE CASCADE,
            card_type flashcard_type NOT NULL DEFAULT 'term_definition',
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            explanation TEXT,
            source_chunk_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            source_pages VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Create flashcard_reviews table
    op.execute("""
        CREATE TABLE flashcard_reviews (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deck_id UUID NOT NULL REFERENCES flashcard_decks(id) ON DELETE CASCADE,
            flashcard_id UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
            rating review_rating NOT NULL,
            reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Add indexes for common queries
    op.execute("CREATE INDEX ix_flashcard_decks_space_id ON flashcard_decks(space_id)")
    op.execute(
        "CREATE INDEX ix_flashcard_decks_document_id ON flashcard_decks(document_id)"
    )
    op.execute("CREATE INDEX ix_flashcards_deck_id ON flashcards(deck_id)")
    op.execute(
        "CREATE INDEX ix_flashcard_reviews_deck_id ON flashcard_reviews(deck_id)"
    )
    op.execute(
        "CREATE INDEX ix_flashcard_reviews_flashcard_id ON flashcard_reviews(flashcard_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS flashcard_reviews")
    op.execute("DROP TABLE IF EXISTS flashcards")
    op.execute("DROP TABLE IF EXISTS flashcard_decks")
    op.execute("DROP TYPE IF EXISTS review_rating")
    op.execute("DROP TYPE IF EXISTS flashcard_type")
