"""Vector search service using pgvector.

Performs cosine similarity searches over document chunk embeddings
stored in PostgreSQL with the pgvector extension.
"""

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk

logger = logging.getLogger(__name__)


async def search_similar_chunks(
    db: AsyncSession,
    query_embedding: list[float],
    top_k: int = 5,
    document_ids: list[uuid.UUID] | None = None,
    score_threshold: float | None = None,
) -> list[dict]:
    """Search for document chunks most similar to the query embedding.

    Uses cosine distance via pgvector's <=> operator with the HNSW index.

    Args:
        db: Async database session.
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

    result = await db.execute(query)
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
