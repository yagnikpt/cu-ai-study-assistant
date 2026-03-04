"""add document_images table for GCS-stored images with multimodal embeddings

Revision ID: 005
Revises: 004
Create Date: 2026-03-04
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── document_images table ──
    op.execute("""
        CREATE TABLE document_images (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            gcs_uri         VARCHAR(1000) NOT NULL,
            page_number     INTEGER,
            image_index     INTEGER NOT NULL,
            mime_type       VARCHAR(100) NOT NULL DEFAULT 'image/png',
            embedding       vector(1408),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Indexes ──
    op.execute(
        "CREATE INDEX idx_document_images_document ON document_images(document_id)"
    )

    # HNSW index for multimodal image embeddings (1408-dim, cosine distance)
    op.execute("""
        CREATE INDEX idx_document_images_embedding
        ON document_images
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_images_embedding")
    op.execute("DROP INDEX IF EXISTS idx_document_images_document")
    op.execute("DROP TABLE IF EXISTS document_images")
