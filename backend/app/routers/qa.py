"""Q&A router - RAG-based question answering with source attribution."""

from fastapi import APIRouter, HTTPException

from app.dependencies import DBSession
from app.schemas.qa import (
    AskRequest,
    AskResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SourceReference,
)
from app.services.embeddings import embed_query
from app.services.qa_service import ask_question
from app.services.vector_search import search_similar_chunks

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])


@router.post("/ask", response_model=AskResponse)
async def ask(db: DBSession, body: AskRequest):
    """Ask a question and get a RAG-grounded answer with citations.

    The system will:
    1. Search your uploaded documents for relevant passages
    2. Generate an answer based ONLY on the found material
    3. Include source citations with page references

    Optionally filter to specific documents using `document_ids`.
    """
    try:
        result = await ask_question(
            db=db,
            question=body.question,
            document_ids=body.document_ids,
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


@router.post("/search", response_model=SearchResponse)
async def semantic_search(db: DBSession, body: SearchRequest):
    """Perform a semantic search over document chunks.

    Returns the most relevant passages without generating an answer.
    Useful for exploring what's in your knowledge base.
    """
    try:
        query_embedding = await embed_query(body.query)
        results = await search_similar_chunks(
            db=db,
            query_embedding=query_embedding,
            top_k=body.top_k,
            document_ids=body.document_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}") from e

    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        query=body.query,
    )
