"""Summary/lesson generation service.

Takes a topic or document section and generates structured educational
summaries with citations to source material.
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from google import genai

from app.config import settings
from app.services.embeddings import embed_query, embed_query_multimodal
from app.services.genai_client import get_genai_client
from app.services.vector_search import search_similar_chunks, search_similar_images

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
6. Cite sources sparingly — only when stating a key fact, definition, or claim that a student might want to verify. Use the exact format from the AVAILABLE SOURCES list: [Source: document_name, p.X | chunk_id=<uuid>]. Place citations at the end of the relevant sentence or paragraph, NOT after every line. A few well-placed citations are better than citing every sentence. Never invent source references.
7. ONLY use information from the provided source material.
8. If the source material is insufficient, note what aspects are not covered.
9. When AVAILABLE IMAGES are provided and an image is relevant to a concept being summarized, insert it inline using exactly this format: [Image: caption | id=<uuid>]. Place it where it would be most helpful for understanding. Only reference images from the AVAILABLE IMAGES list — never invent image references. You may reference zero, one, or multiple images depending on relevance.

Output format: Markdown with proper headers (##, ###) and bullet points.
"""

DETAIL_INSTRUCTIONS = {
    "brief": "Create a concise summary (3-5 key points) of the topic.",
    "standard": "Create a comprehensive summary covering all major concepts, with examples where available.",
    "detailed": "Create a thorough, detailed summary. Include all concepts, sub-topics, examples, formulas, and definitions found in the source material.",
}


async def _retrieve_chunks(
    db: AsyncSession,
    topic: str | None = None,
    document_id: uuid.UUID | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    space_id: uuid.UUID | None = None,
) -> tuple[list[dict], str]:
    """Shared chunk retrieval for both streaming and non-streaming.

    Returns (chunks, effective_topic).
    """
    chunks: list[dict] = []
    effective_topic = topic or "General summary"

    if document_id and page_start is not None and page_end is not None:
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
            sections = [c["section_title"] for c in chunks if c.get("section_title")]
            effective_topic = (
                sections[0] if sections else f"Pages {page_start}-{page_end}"
            )

    elif topic:
        query_embedding = await embed_query(topic)
        # If space_id is provided, restrict to space docs; else use doc_id if given
        doc_ids = None
        if document_id:
            doc_ids = [document_id]
        elif space_id:
            result = await db.execute(
                select(Document.id).where(
                    Document.space_id == space_id, Document.status == "ready"
                )
            )
            doc_ids = list(result.scalars().all())
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

    return chunks, effective_topic


def _build_summary_prompt(
    chunks: list[dict],
    effective_topic: str,
    detail_level: str,
    image_results: list[dict] | None = None,
) -> str:
    """Build the user prompt from chunks, topic, and detail level."""
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
    image_context = _build_image_context(image_results or [])
    source_context = _build_source_context(chunks)

    return f"""Create a structured educational summary about: {effective_topic}

{DETAIL_INSTRUCTIONS.get(detail_level, DETAIL_INSTRUCTIONS["standard"])}

SOURCE MATERIAL:
{context}
{image_context}
{source_context}

Generate the summary in markdown format. Embed relevant images inline using the [Image: caption | id=<uuid>] format where helpful."""


def _build_source_list(chunks: list[dict]) -> list[dict]:
    """Build source list from chunks."""
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
                "chunk_id": str(chunk["chunk_id"]),
                "document_id": str(chunk["document_id"]),
            }
        )
    return sources


def _build_image_dicts(images: list[dict]) -> list[dict]:
    """Build image reference dicts from retrieved images."""
    return [
        {
            "image_id": img["image_id"],
            "image_url": img["image_url"],
            "document_id": str(img["document_id"]),
            "document_name": img["document_name"],
            "page_number": img.get("page_number"),
            "caption": img.get("caption"),
            "relevance_score": img["score"],
        }
        for img in images
    ]


def _build_image_context(images: list[dict]) -> str:
    """Build the AVAILABLE IMAGES section of the prompt from retrieved images."""
    if not images:
        return ""

    parts = ["\nAVAILABLE IMAGES:"]
    for img in images:
        caption = img.get("caption") or "Untitled image"
        page = f", p.{img['page_number']}" if img.get("page_number") else ""
        parts.append(
            f"- [Image: {caption} | id={img['image_id']}] "
            f"(from {img['document_name']}{page})"
        )
    return "\n".join(parts)


def _build_source_context(chunks: list[dict]) -> str:
    """Build the AVAILABLE SOURCES section of the prompt from retrieved chunks."""
    if not chunks:
        return ""

    parts = ["\nAVAILABLE SOURCES:"]
    for chunk in chunks:
        pages = (
            f"p.{chunk['page_start']}"
            if chunk["page_start"] == chunk["page_end"]
            else f"pp.{chunk['page_start']}-{chunk['page_end']}"
        )
        section = (
            f" Section: {chunk['section_title']}" if chunk.get("section_title") else ""
        )
        parts.append(
            f"- [Source: {chunk['document_name']}, {pages} | chunk_id={chunk['chunk_id']}]"
            f"{section}"
        )
    return "\n".join(parts)


async def _retrieve_images(
    db: AsyncSession,
    topic: str,
    document_ids: list[uuid.UUID] | None = None,
) -> list[dict]:
    """Retrieve relevant images for the given topic via multimodal embedding search."""
    try:
        mm_embedding = await embed_query_multimodal(topic)
        return await search_similar_images(
            db=db,
            query_embedding=mm_embedding,
            top_k=3,
            document_ids=document_ids,
        )
    except Exception:
        logger.warning("Image search failed, continuing without images", exc_info=True)
        return []


async def generate_summary(
    db: AsyncSession,
    topic: str | None = None,
    document_id: uuid.UUID | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    detail_level: str = "standard",
    space_id: uuid.UUID | None = None,
) -> dict:
    """Generate a structured summary from course materials.

    Can work in two modes:
    1. Topic-based: Search for relevant chunks across documents.
    2. Document-based: Summarize specific pages of a document.

    Returns:
        Dict with 'summary' (markdown), 'topic', 'sources', 'images', and 'model'.
    """
    chunks, effective_topic = await _retrieve_chunks(
        db, topic, document_id, page_start, page_end, space_id=space_id
    )

    if not chunks:
        return {
            "summary": "No relevant source material was found for this topic.",
            "topic": effective_topic,
            "sources": [],
            "images": [],
            "model": settings.generation_model,
        }

    # Retrieve relevant images
    doc_ids = [document_id] if document_id else None
    if not doc_ids and space_id:
        result = await db.execute(
            select(Document.id).where(
                Document.space_id == space_id, Document.status == "ready"
            )
        )
        doc_ids = list(result.scalars().all())
    image_results = await _retrieve_images(db, effective_topic, doc_ids)

    user_prompt = _build_summary_prompt(
        chunks, effective_topic, detail_level, image_results
    )

    client = get_genai_client()
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
    sources = _build_source_list(chunks)
    images = _build_image_dicts(image_results)

    logger.info(
        f"Generated {detail_level} summary for topic: {effective_topic} "
        f"with {len(sources)} sources and {len(images)} images"
    )

    return {
        "summary": summary,
        "topic": effective_topic,
        "sources": sources,
        "images": images,
        "model": settings.generation_model,
    }


async def generate_summary_stream(
    db: AsyncSession,
    topic: str | None = None,
    document_id: uuid.UUID | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    detail_level: str = "standard",
    space_id: uuid.UUID | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a summary as SSE events.

    Yields SSE-formatted strings:
      event: meta\ndata: <json>\n\n       (topic + sources, sent first)
      event: images\ndata: <json>\n\n     (relevant images, sent after meta)
      event: token\ndata: <json>\n\n      (for each text chunk)
      event: done\ndata: <json>\n\n       (sent last)
    """
    chunks, effective_topic = await _retrieve_chunks(
        db, topic, document_id, page_start, page_end, space_id=space_id
    )

    if not chunks:
        meta = {
            "topic": effective_topic,
            "sources": [],
        }
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
        yield f"event: token\ndata: {json.dumps('No relevant source material was found for this topic.')}\n\n"
        yield f"event: done\ndata: {json.dumps({'model': settings.generation_model})}\n\n"
        return

    sources = _build_source_list(chunks)

    # Emit metadata (topic + sources) first
    meta = {
        "topic": effective_topic,
        "sources": sources,
    }
    yield f"event: meta\ndata: {json.dumps(meta)}\n\n"

    # Retrieve and emit relevant images
    doc_ids = [document_id] if document_id else None
    if not doc_ids and space_id:
        result = await db.execute(
            select(Document.id).where(
                Document.space_id == space_id, Document.status == "ready"
            )
        )
        doc_ids = list(result.scalars().all())
    image_results = await _retrieve_images(db, effective_topic, doc_ids)
    images = _build_image_dicts(image_results)
    if images:
        yield f"event: images\ndata: {json.dumps(images)}\n\n"

    # Stream generation
    user_prompt = _build_summary_prompt(
        chunks, effective_topic, detail_level, image_results
    )
    client = get_genai_client()
    stream = await client.aio.models.generate_content_stream(
        model=settings.generation_model,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SUMMARY_SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=4096,
        ),
    )

    async for chunk in stream:
        text = chunk.text
        if text:
            yield f"event: token\ndata: {json.dumps(text)}\n\n"

    yield f"event: done\ndata: {json.dumps({'model': settings.generation_model})}\n\n"
    logger.info(
        f"Streamed {detail_level} summary for topic: {effective_topic} "
        f"with {len(sources)} sources and {len(images)} images"
    )
