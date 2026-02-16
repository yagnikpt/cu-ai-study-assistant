"""Summary/lesson generation service.

Takes a topic or document section and generates structured educational
summaries with citations to source material.
"""

import logging
import uuid

from google import genai

from app.config import settings
from app.services.embeddings import embed_query
from app.services.vector_search import search_similar_chunks

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """You are an AI study assistant that creates structured educational summaries.

Your summaries should:
1. Start with a brief overview of the topic.
2. Break down key concepts into clear, digestible sections using markdown headers.
3. Include relevant examples or analogies when present in the source material.
4. Use bullet points for lists of related items.
5. Highlight important definitions or formulas.
6. ALWAYS cite sources using [Source: document_name, p.X] format.
7. ONLY use information from the provided source material.
8. If the source material is insufficient, note what aspects are not covered.

Output format: Markdown with proper headers (##, ###), bullet points, and inline citations.
"""


async def generate_summary(
    db: AsyncSession,
    topic: str | None = None,
    document_id: uuid.UUID | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    detail_level: str = "standard",
) -> dict:
    """Generate a structured summary from course materials.

    Can work in two modes:
    1. Topic-based: Search for relevant chunks across documents.
    2. Document-based: Summarize specific pages of a document.

    Args:
        db: Async database session.
        topic: Topic to summarize (used for vector search).
        document_id: Specific document to summarize from.
        page_start: Start page for document-based summary.
        page_end: End page for document-based summary.
        detail_level: 'brief', 'standard', or 'detailed'.

    Returns:
        Dict with 'summary' (markdown), 'topic', 'sources', and 'model'.
    """
    chunks: list[dict] = []
    effective_topic = topic or "General summary"

    if document_id and page_start is not None and page_end is not None:
        # Mode 2: Direct page range retrieval
        query = (
            select(DocumentChunk, Document.original_filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.page_start >= page_start)
            .where(DocumentChunk.page_end <= page_end)
            .order_by(DocumentChunk.chunk_index)
        )
        result = await db.execute(query)
        rows = result.all()

        for chunk, doc_name in rows:
            chunks.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_name": doc_name,
                    "content": chunk.content,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "section_title": chunk.section_title,
                    "score": 1.0,
                }
            )

        if not effective_topic or effective_topic == "General summary":
            # Try to derive topic from the chunks
            sections = [c["section_title"] for c in chunks if c.get("section_title")]
            effective_topic = (
                sections[0] if sections else f"Pages {page_start}-{page_end}"
            )

    elif topic:
        # Mode 1: Topic-based vector search
        query_embedding = await embed_query(topic)
        doc_ids = [document_id] if document_id else None
        chunks = await search_similar_chunks(
            db=db,
            query_embedding=query_embedding,
            top_k=10,
            document_ids=doc_ids,
        )
    else:
        raise ValueError(
            "Either 'topic' or 'document_id' with page range must be provided."
        )

    if not chunks:
        return {
            "summary": "No relevant source material was found for this topic.",
            "topic": effective_topic,
            "sources": [],
            "model": settings.generation_model,
        }

    # Build context from chunks
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        pages = (
            f"p.{chunk['page_start']}"
            if chunk["page_start"] == chunk["page_end"]
            else f"pp.{chunk['page_start']}-{chunk['page_end']}"
        )
        section = (
            f" | Section: {chunk['section_title']}"
            if chunk.get("section_title")
            else ""
        )
        header = f"[Source {i}: {chunk['document_name']}, {pages}{section}]"
        context_parts.append(f"{header}\n{chunk['content']}")

    context = "\n\n---\n\n".join(context_parts)

    # Adjust prompt based on detail level
    detail_instructions = {
        "brief": "Create a concise summary (3-5 key points) of the topic.",
        "standard": "Create a comprehensive summary covering all major concepts, with examples where available.",
        "detailed": "Create a thorough, detailed summary. Include all concepts, sub-topics, examples, formulas, and definitions found in the source material.",
    }

    user_prompt = f"""Create a structured educational summary about: {effective_topic}

{detail_instructions.get(detail_level, detail_instructions["standard"])}

SOURCE MATERIAL:
{context}

Generate the summary in markdown format with proper citations."""

    # Generate with Gemini
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SUMMARY_SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=4096,
        ),
    )

    summary = response.text or "Unable to generate summary."

    # Build source list
    sources = []
    for chunk in chunks:
        pages = (
            f"p.{chunk['page_start']}"
            if chunk["page_start"] == chunk["page_end"]
            else f"pp.{chunk['page_start']}-{chunk['page_end']}"
        )
        sources.append(
            {
                "document_name": chunk["document_name"],
                "pages": pages,
                "chunk_id": chunk["chunk_id"],
            }
        )

    logger.info(f"Generated {detail_level} summary for topic: {effective_topic}")

    return {
        "summary": summary,
        "topic": effective_topic,
        "sources": sources,
        "model": settings.generation_model,
    }
