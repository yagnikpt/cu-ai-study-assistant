"""Summary generation router."""

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.dependencies import DBSession
from app.models import Document, Space
from app.schemas.summary import (
    SummaryRequest,
    SummaryResponse,
    SummarySource,
    SummaryImageReference,
)
from app.services.summary_service import generate_summary, generate_summary_stream

router = APIRouter(prefix="/api/v1/spaces/{space_id}/summaries", tags=["summaries"])


async def _get_space_doc_ids(db, space_id: uuid.UUID) -> list[uuid.UUID]:
    """Get all ready document IDs belonging to a space."""
    space = await db.get(Space, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    result = await db.execute(
        select(Document.id).where(
            Document.space_id == space_id, Document.status == "ready"
        )
    )
    return list(result.scalars().all())


@router.post("/generate", response_model=SummaryResponse)
async def create_summary(db: DBSession, space_id: uuid.UUID, body: SummaryRequest):
    """Generate a structured educational summary.

    Two modes:
    1. **Topic-based**: Provide a `topic` to search across space documents.
    2. **Page-range**: Provide `document_id` + `page_start`/`page_end` to
       summarize specific pages.

    The `detail_level` controls summary depth:
    - `brief`: 3-5 key points
    - `standard`: Comprehensive coverage
    - `detailed`: Everything including formulas, examples, definitions
    """
    if not body.topic and not body.document_id:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'topic' or 'document_id' (with optional page range).",
        )

    # Validate that document belongs to this space if provided
    if body.document_id:
        space_doc_ids = await _get_space_doc_ids(db, space_id)
        if body.document_id not in space_doc_ids:
            raise HTTPException(
                status_code=400,
                detail="The specified document does not belong to this space.",
            )

    try:
        result = await generate_summary(
            db=db,
            topic=body.topic,
            document_id=body.document_id,
            page_start=body.page_start,
            page_end=body.page_end,
            detail_level=body.detail_level,
            space_id=space_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Summary generation failed: {e}"
        ) from e

    return SummaryResponse(
        summary=result["summary"],
        topic=result["topic"],
        sources=[SummarySource(**s) for s in result["sources"]],
        images=[SummaryImageReference(**i) for i in result.get("images", [])],
        model=result["model"],
    )


@router.post("/generate/stream")
async def create_summary_stream(
    db: DBSession, space_id: uuid.UUID, body: SummaryRequest
):
    """Stream a summary as Server-Sent Events.

    SSE events emitted:
      - `meta`: JSON object with `topic` and `sources` (sent first)
      - `images`: JSON array of image references (sent after meta, optional)
      - `token`: JSON string with a text fragment (many times)
      - `done`: JSON object with `model` field (sent last)
    """
    if not body.topic and not body.document_id:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'topic' or 'document_id' (with optional page range).",
        )

    if body.document_id:
        space_doc_ids = await _get_space_doc_ids(db, space_id)
        if body.document_id not in space_doc_ids:
            raise HTTPException(
                status_code=400,
                detail="The specified document does not belong to this space.",
            )

    try:
        event_stream = generate_summary_stream(
            db=db,
            topic=body.topic,
            document_id=body.document_id,
            page_start=body.page_start,
            page_end=body.page_end,
            detail_level=body.detail_level,
            space_id=space_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
