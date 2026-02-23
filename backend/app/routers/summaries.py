"""Summary generation router."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies import DBSession
from app.schemas.summary import SummaryRequest, SummaryResponse, SummarySource
from app.services.summary_service import generate_summary, generate_summary_stream

router = APIRouter(prefix="/api/v1/summaries", tags=["summaries"])


@router.post("/generate", response_model=SummaryResponse)
async def create_summary(db: DBSession, body: SummaryRequest):
    """Generate a structured educational summary.

    Two modes:
    1. **Topic-based**: Provide a `topic` to search across all documents.
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

    try:
        result = await generate_summary(
            db=db,
            topic=body.topic,
            document_id=body.document_id,
            page_start=body.page_start,
            page_end=body.page_end,
            detail_level=body.detail_level,
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
        model=result["model"],
    )


@router.post("/generate/stream")
async def create_summary_stream(db: DBSession, body: SummaryRequest):
    """Stream a summary as Server-Sent Events.

    SSE events emitted:
      - `meta`: JSON object with `topic` and `sources` (sent first)
      - `token`: JSON string with a text fragment (many times)
      - `done`: JSON object with `model` field (sent last)
    """
    if not body.topic and not body.document_id:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'topic' or 'document_id' (with optional page range).",
        )

    try:
        event_stream = generate_summary_stream(
            db=db,
            topic=body.topic,
            document_id=body.document_id,
            page_start=body.page_start,
            page_end=body.page_end,
            detail_level=body.detail_level,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
