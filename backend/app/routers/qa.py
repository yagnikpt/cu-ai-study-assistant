"""Q&A router - RAG-based question answering with source attribution."""

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.dependencies import DBSession
from app.models import Document, Space
from app.schemas.qa import (
    AskRequest,
    AskResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SourceReference,
)
from app.services.embeddings import embed_query
from app.services.qa_service import ask_question, ask_question_stream
from app.services.vector_search import search_similar_chunks

router = APIRouter(prefix="/api/v1/spaces/{space_id}/qa", tags=["qa"])


async def _get_space_doc_ids(db, space_id: uuid.UUID) -> list[uuid.UUID]:
    """Get all document IDs belonging to a space."""
    space = await db.get(Space, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    result = await db.execute(
        select(Document.id).where(
            Document.space_id == space_id, Document.status == "ready"
        )
    )
    return list(result.scalars().all())


@router.post("/ask", response_model=AskResponse)
async def ask(db: DBSession, space_id: uuid.UUID, body: AskRequest):
    """Ask a question and get a RAG-grounded answer with citations.

    The system will:
    1. Search your uploaded documents for relevant passages
    2. Generate an answer based ONLY on the found material
    3. Include source citations with page references

    Optionally filter to specific documents using `document_ids`.
    If not provided, all documents in this space are searched.
    """
    # Scope to this space's documents
    space_doc_ids = await _get_space_doc_ids(db, space_id)
    if not space_doc_ids:
        raise HTTPException(
            status_code=400,
            detail="No ready documents in this space. Upload and process documents first.",
        )

    # Use user-provided doc_ids only if they're within this space
    doc_ids = body.document_ids
    if doc_ids:
        doc_ids = [d for d in doc_ids if d in space_doc_ids]
        if not doc_ids:
            raise HTTPException(
                status_code=400,
                detail="None of the specified documents belong to this space.",
            )
    else:
        doc_ids = space_doc_ids

    try:
        result = await ask_question(
            db=db,
            question=body.question,
            document_ids=doc_ids,
            top_k=body.top_k,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate answer: {e}"
        ) from e

    return AskResponse(
        answer=result["answer"],
        sources=[SourceReference(**s) for s in result["sources"]],
        model=result["model"],
    )


@router.post("/ask/stream")
async def ask_stream(db: DBSession, space_id: uuid.UUID, body: AskRequest):
    """Stream a RAG-grounded answer as Server-Sent Events.

    SSE events emitted:
      - `sources`: JSON array of source references (sent first)
      - `token`: JSON string with a text fragment (many times)
      - `done`: JSON object with `model` field (sent last)
    """
    space_doc_ids = await _get_space_doc_ids(db, space_id)
    if not space_doc_ids:
        raise HTTPException(
            status_code=400,
            detail="No ready documents in this space.",
        )

    doc_ids = body.document_ids
    if doc_ids:
        doc_ids = [d for d in doc_ids if d in space_doc_ids]
        if not doc_ids:
            raise HTTPException(
                status_code=400,
                detail="None of the specified documents belong to this space.",
            )
    else:
        doc_ids = space_doc_ids

    try:
        event_stream = ask_question_stream(
            db=db,
            question=body.question,
            document_ids=doc_ids,
            top_k=body.top_k,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/search", response_model=SearchResponse)
async def semantic_search(db: DBSession, space_id: uuid.UUID, body: SearchRequest):
    """Perform a semantic search over document chunks in this space.

    Returns the most relevant passages without generating an answer.
    Useful for exploring what's in your knowledge base.
    """
    space_doc_ids = await _get_space_doc_ids(db, space_id)
    if not space_doc_ids:
        raise HTTPException(
            status_code=400,
            detail="No ready documents in this space.",
        )

    doc_ids = body.document_ids
    if doc_ids:
        doc_ids = [d for d in doc_ids if d in space_doc_ids]
        if not doc_ids:
            raise HTTPException(
                status_code=400,
                detail="None of the specified documents belong to this space.",
            )
    else:
        doc_ids = space_doc_ids

    try:
        query_embedding = await embed_query(body.query)
        results = await search_similar_chunks(
            db=db,
            query_embedding=query_embedding,
            top_k=body.top_k,
            document_ids=doc_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}") from e

    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        query=body.query,
    )
