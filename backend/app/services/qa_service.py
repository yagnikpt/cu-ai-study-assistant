"""RAG-based Q&A service.

Retrieves relevant document chunks via vector search, constructs a
grounded prompt, and generates answers using Gemini with source citations.
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from google import genai

from app.config import settings
from app.services.genai_client import get_genai_client
from app.services.embeddings import embed_query, embed_query_multimodal
from app.services.vector_search import search_similar_chunks, search_similar_images

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI study assistant that helps students understand their course materials.

IMPORTANT RULES:
1. ONLY answer based on the provided source material below. Do NOT use external knowledge.
2. If the source material does not contain enough information to answer the question, say so explicitly.
3. Cite sources sparingly — only when introducing a key fact, definition, or claim that a student might want to verify. Use the exact format from the AVAILABLE SOURCES list: [Source: document_name, p.X | chunk_id=<uuid>]. Place citations at the end of the relevant sentence or paragraph, NOT after every line. A few well-placed citations are better than citing every sentence. Never invent source references.
4. Be clear, educational, and well-structured in your explanations.
5. Use markdown formatting for readability.
6. Break down complex concepts into simpler parts when helpful.
7. When AVAILABLE IMAGES are provided and an image is relevant to your explanation, insert it inline using exactly this format: [Image: caption | id=<uuid>]. Place it where it would be most helpful for understanding. Only reference images from the AVAILABLE IMAGES list — never invent image references. You may reference zero, one, or multiple images depending on relevance.

Output format: Markdown with proper headers (##, ###), bullet points.
"""


def _build_context_prompt(chunks: list[dict]) -> str:
    """Build the context section of the prompt from retrieved chunks."""
    if not chunks:
        return "No relevant source material was found."

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

    return "\n\n---\n\n".join(context_parts)


def _build_source_dicts(chunks: list[dict]) -> list[dict]:
    """Build source reference dicts from retrieved chunks."""
    sources = []
    for chunk in chunks:
        sources.append(
            {
                "chunk_id": str(chunk["chunk_id"]),
                "document_id": str(chunk["document_id"]),
                "document_name": chunk["document_name"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "section_title": chunk.get("section_title"),
                "relevance_score": chunk["score"],
                "text_preview": chunk["content"][:200] + "..."
                if len(chunk["content"]) > 200
                else chunk["content"],
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


async def _retrieve_and_build_prompt(
    db: Session,
    question: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
) -> tuple[list[dict], list[dict], str]:
    """Shared retrieval + prompt construction for both streaming and non-streaming.

    Returns:
        Tuple of (text chunks, image results, user prompt string).
    """
    # Run text and image embedding in parallel conceptually
    # (both are fast network calls)
    query_embedding = await embed_query(question)
    chunks = search_similar_chunks(
        db=db,
        query_embedding=query_embedding,
        top_k=top_k,
        document_ids=document_ids,
    )

    # Search for relevant images (top 3, in the multimodal embedding space)
    image_results: list[dict] = []
    try:
        mm_embedding = await embed_query_multimodal(question)
        image_results = search_similar_images(
            db=db,
            query_embedding=mm_embedding,
            top_k=3,
            document_ids=document_ids,
        )
    except Exception:
        logger.warning("Image search failed, continuing without images", exc_info=True)

    context = _build_context_prompt(chunks)
    image_context = _build_image_context(image_results)
    source_context = _build_source_context(chunks)
    user_prompt = f"""Based on the following source material, answer the student's question.

SOURCE MATERIAL:
{context}
{image_context}
{source_context}

STUDENT'S QUESTION:
{question}

Provide a clear, well-structured answer. Embed relevant images inline using the [Image: caption | id=<uuid>] format where helpful."""
    return chunks, image_results, user_prompt


async def ask_question(
    db: Session,
    question: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
) -> dict:
    """Answer a question using RAG: retrieve relevant chunks, then generate.

    Args:
        db: Database session.
        question: The user's question.
        document_ids: Optional filter to specific documents.
        top_k: Number of chunks to retrieve for context.

    Returns:
        Dict with 'answer', 'sources', and 'model'.
    """
    chunks, image_results, user_prompt = await _retrieve_and_build_prompt(
        db, question, document_ids, top_k
    )

    client = get_genai_client()
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=2048,
        ),
    )

    answer = (
        response.text
        or "I was unable to generate an answer. Please try rephrasing your question."
    )

    sources = _build_source_dicts(chunks)
    images = _build_image_dicts(image_results)
    logger.info(
        f"Q&A: answered question with {len(sources)} sources and {len(images)} images"
    )

    return {
        "answer": answer,
        "sources": sources,
        "images": images,
        "model": settings.generation_model,
    }


async def ask_question_stream(
    db: Session,
    question: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
) -> AsyncGenerator[str, None]:
    """Stream a RAG answer as SSE events.

    Yields SSE-formatted strings:
      event: sources\ndata: <json>\n\n   (sent first)
      event: images\ndata: <json>\n\n    (sent after sources)
      event: token\ndata: <json>\n\n     (for each text chunk)
      event: done\ndata: <json>\n\n      (sent last)
    """
    chunks, image_results, user_prompt = await _retrieve_and_build_prompt(
        db, question, document_ids, top_k
    )

    # Emit sources first so the client has them while tokens stream
    sources = _build_source_dicts(chunks)
    yield f"event: sources\ndata: {json.dumps(sources)}\n\n"

    # Emit relevant images
    images = _build_image_dicts(image_results)
    if images:
        yield f"event: images\ndata: {json.dumps(images)}\n\n"

    # Stream generation
    client = get_genai_client()
    stream = await client.aio.models.generate_content_stream(
        model=settings.generation_model,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=2048,
        ),
    )

    async for chunk in stream:
        text = chunk.text
        if text:
            yield f"event: token\ndata: {json.dumps(text)}\n\n"

    yield f"event: done\ndata: {json.dumps({'model': settings.generation_model})}\n\n"
    logger.info(
        f"Q&A: streamed answer with {len(sources)} sources and {len(images)} images"
    )
