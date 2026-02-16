"""initial schema - documents, chunks, tags, quizzes

Revision ID: 001
Revises:
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── Document status enum ──
    op.execute("""
        CREATE TYPE document_status AS ENUM ('processing', 'ready', 'failed')
    """)

    # ── Question type enum ──
    op.execute("""
        CREATE TYPE question_type AS ENUM ('mcq', 'short_answer')
    """)

    # ── Documents table ──
    op.execute("""
        CREATE TABLE documents (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            filename        VARCHAR(500) NOT NULL,
            original_filename VARCHAR(500) NOT NULL,
            file_path       VARCHAR(1000) NOT NULL,
            file_size_bytes BIGINT NOT NULL,
            page_count      INTEGER NOT NULL DEFAULT 0,
            course_name     VARCHAR(255),
            subject         VARCHAR(255),
            status          document_status NOT NULL DEFAULT 'processing',
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Document chunks table (with pgvector embedding) ──
    op.execute("""
        CREATE TABLE document_chunks (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            content         TEXT NOT NULL,
            chunk_index     INTEGER NOT NULL,
            page_start      INTEGER NOT NULL,
            page_end        INTEGER NOT NULL,
            section_title   VARCHAR(500),
            embedding       vector(768),
            token_count     INTEGER NOT NULL DEFAULT 0,
            metadata        JSONB NOT NULL DEFAULT '{}',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Tags table ──
    op.execute("""
        CREATE TABLE tags (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name            VARCHAR(100) NOT NULL UNIQUE,
            color           VARCHAR(7),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Document-Tags association (many-to-many) ──
    op.execute("""
        CREATE TABLE document_tags (
            document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            tag_id          UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (document_id, tag_id)
        )
    """)

    # ── Quizzes table ──
    op.execute("""
        CREATE TABLE quizzes (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            title           VARCHAR(500) NOT NULL,
            document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
            topic           VARCHAR(500),
            question_count  INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Quiz questions table ──
    op.execute("""
        CREATE TABLE quiz_questions (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            quiz_id         UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
            question_type   question_type NOT NULL DEFAULT 'mcq',
            question_text   TEXT NOT NULL,
            options         JSONB,
            correct_answer  TEXT NOT NULL,
            explanation     TEXT,
            source_chunk_ids JSONB NOT NULL DEFAULT '[]',
            source_pages    VARCHAR(100),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Quiz attempts table ──
    op.execute("""
        CREATE TABLE quiz_attempts (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            quiz_id         UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
            question_id     UUID NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
            user_answer     TEXT NOT NULL,
            is_correct      BOOLEAN NOT NULL DEFAULT FALSE,
            feedback        TEXT,
            attempted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Indexes ──

    # Document lookups
    op.execute("CREATE INDEX idx_documents_status ON documents(status)")
    op.execute("CREATE INDEX idx_documents_course ON documents(course_name)")
    op.execute("CREATE INDEX idx_documents_created ON documents(created_at DESC)")

    # Chunk lookups by document
    op.execute("CREATE INDEX idx_chunks_document ON document_chunks(document_id)")
    op.execute(
        "CREATE INDEX idx_chunks_document_order ON document_chunks(document_id, chunk_index)"
    )

    # HNSW index for vector similarity search (cosine distance)
    # This is the key index that makes RAG retrieval fast
    op.execute("""
        CREATE INDEX idx_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Tag lookups
    op.execute("CREATE INDEX idx_tags_name ON tags(name)")

    # Quiz lookups
    op.execute("CREATE INDEX idx_quizzes_document ON quizzes(document_id)")
    op.execute("CREATE INDEX idx_quiz_questions_quiz ON quiz_questions(quiz_id)")
    op.execute("CREATE INDEX idx_quiz_attempts_quiz ON quiz_attempts(quiz_id)")
    op.execute("CREATE INDEX idx_quiz_attempts_question ON quiz_attempts(question_id)")

    # Updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # Auto-update updated_at on documents
    op.execute("""
        CREATE TRIGGER trigger_documents_updated_at
        BEFORE UPDATE ON documents
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trigger_documents_updated_at ON documents")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # Drop tables in reverse dependency order
    op.execute("DROP TABLE IF EXISTS quiz_attempts")
    op.execute("DROP TABLE IF EXISTS quiz_questions")
    op.execute("DROP TABLE IF EXISTS quizzes")
    op.execute("DROP TABLE IF EXISTS document_tags")
    op.execute("DROP TABLE IF EXISTS tags")
    op.execute("DROP TABLE IF EXISTS document_chunks")
    op.execute("DROP TABLE IF EXISTS documents")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS question_type")
    op.execute("DROP TYPE IF EXISTS document_status")

    # Don't drop extensions (they may be used by other schemas)
