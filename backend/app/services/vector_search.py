"""Vector search service using pgvector.

Performs cosine similarity searches over document chunk embeddings
and image embeddings stored in PostgreSQL with the pgvector extension.
"""

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentImage
from app.services.storage import get_public_url

logger = logging.getLogger(__name__)


def search_similar_chunks(
    db: Session,
    query_embedding: list[float],
    top_k: int = 5,
    document_ids: list[uuid.UUID] | None = None,
    score_threshold: float | None = None,
) -> list[dict]:
    """Search for document chunks most similar to the query embedding.

    Uses cosine distance via pgvector's <=> operator with the HNSW index.

    Args:
        db: Database session.
        query_embedding: The query embedding vector (768-dim).
        top_k: Number of results to return.
        document_ids: Optional filter to specific documents.
        score_threshold: Optional maximum cosine distance to include.

    Returns:
        List of dicts with chunk data and similarity scores, sorted by relevance.
    """
    # Build the query using pgvector's cosine distance operator
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # Base query: select chunks with cosine distance
    query = (
        select(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
            Document.original_filename,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.embedding.is_not(None))
        .where(Document.status == "ready")
    )

    # Filter by document IDs if provided
    if document_ids:
        query = query.where(DocumentChunk.document_id.in_(document_ids))

    # Filter by score threshold if provided
    if score_threshold is not None:
        query = query.where(
            DocumentChunk.embedding.cosine_distance(query_embedding) < score_threshold
        )

    # Order by cosine distance (ascending = most similar first)
    query = query.order_by(text("distance")).limit(top_k)

    result = db.execute(query)
    rows = result.all()

    results = []
    for chunk, distance, doc_name in rows:
        # Convert cosine distance to similarity score (1 - distance)
        similarity_score = 1.0 - distance

        results.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_name": doc_name,
                "content": chunk.content,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "section_title": chunk.section_title,
                "chunk_index": chunk.chunk_index,
                "score": round(similarity_score, 4),
            }
        )

    logger.info(f"Vector search returned {len(results)} results (top_k={top_k})")
    return results


def search_similar_images(
    db: Session,
    query_embedding: list[float],
    top_k: int = 3,
    document_ids: list[uuid.UUID] | None = None,
    score_threshold: float | None = None,
) -> list[dict]:
    """Search for document images most similar to the query embedding.

    Uses cosine distance via pgvector's <=> operator with the HNSW index
    on the 1408-dim multimodal embeddings.

    Args:
        db: Database session.
        query_embedding: The query embedding vector (1408-dim).
        top_k: Number of results to return.
        document_ids: Optional filter to specific documents.
        score_threshold: Optional maximum cosine distance to include.

    Returns:
        List of dicts with image data and similarity scores, sorted by relevance.
    """
    query = (
        select(
            DocumentImage,
            DocumentImage.embedding.cosine_distance(query_embedding).label("distance"),
            Document.original_filename,
        )
        .join(Document, DocumentImage.document_id == Document.id)
        .where(DocumentImage.embedding.is_not(None))
        .where(Document.status == "ready")
    )

    if document_ids:
        query = query.where(DocumentImage.document_id.in_(document_ids))

    if score_threshold is not None:
        query = query.where(
            DocumentImage.embedding.cosine_distance(query_embedding) < score_threshold
        )

    query = query.order_by(text("distance")).limit(top_k)

    result = db.execute(query)
    rows = result.all()

    results = []
    for image, distance, doc_name in rows:
        similarity_score = 1.0 - distance

        results.append(
            {
                "image_id": str(image.id),
                "document_id": image.document_id,
                "document_name": doc_name,
                "image_url": get_public_url(image.gcs_uri),
                "page_number": image.page_number,
                "mime_type": image.mime_type,
                "caption": image.caption,
                "score": round(similarity_score, 4),
            }
        )

    logger.info(f"Image vector search returned {len(results)} results (top_k={top_k})")
    return results
