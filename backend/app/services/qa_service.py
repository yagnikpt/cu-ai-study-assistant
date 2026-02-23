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
from app.services.embeddings import embed_query
from app.services.vector_search import search_similar_chunks

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI study assistant that helps students understand their course materials.

IMPORTANT RULES:
1. ONLY answer based on the provided source material below. Do NOT use external knowledge.
2. If the source material does not contain enough information to answer the question, say so explicitly.
3. Always cite your sources using the format [Source: document_name, p.X] or [Source: document_name, pp.X-Y].
4. Be clear, educational, and well-structured in your explanations.;
5. Use markdown formatting for readability.
6. Break down complex concepts into simpler parts when helpful.

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


async def _retrieve_and_build_prompt(
    db: AsyncSession,
    question: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
) -> tuple[list[dict], str]:
    """Shared retrieval + prompt construction for both streaming and non-streaming."""
    query_embedding = await embed_query(question)
    chunks = await search_similar_chunks(
        db=db,
        query_embedding=query_embedding,
        top_k=top_k,
        document_ids=document_ids,
    )
    context = _build_context_prompt(chunks)
    user_prompt = f"""Based on the following source material, answer the student's question.

SOURCE MATERIAL:
{context}

STUDENT'S QUESTION:
{question}

Provide a clear, well-structured answer with source citations."""
    return chunks, user_prompt


async def ask_question(
    db: AsyncSession,
    question: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
) -> dict:
    """Answer a question using RAG: retrieve relevant chunks, then generate.

    Args:
        db: Async database session.
        question: The user's question.
        document_ids: Optional filter to specific documents.
        top_k: Number of chunks to retrieve for context.

    Returns:
        Dict with 'answer', 'sources', and 'model'.
    """
    chunks, user_prompt = await _retrieve_and_build_prompt(
        db, question, document_ids, top_k
    )

    client = genai.Client(api_key=settings.gemini_api_key)
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
    logger.info(f"Q&A: answered question with {len(sources)} sources")

    return {
        "answer": answer,
        "sources": sources,
        "model": settings.generation_model,
    }


async def ask_question_stream(
    db: AsyncSession,
    question: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
) -> AsyncGenerator[str, None]:
    """Stream a RAG answer as SSE events.

    Yields SSE-formatted strings:
      event: sources\ndata: <json>\n\n   (sent first)
      event: token\ndata: <json>\n\n     (for each text chunk)
      event: done\ndata: <json>\n\n      (sent last)
    """
    chunks, user_prompt = await _retrieve_and_build_prompt(
        db, question, document_ids, top_k
    )

    # Emit sources first so the client has them while tokens stream
    sources = _build_source_dicts(chunks)
    yield f"event: sources\ndata: {json.dumps(sources)}\n\n"

    # Stream generation
    client = genai.Client(api_key=settings.gemini_api_key)
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
    logger.info(f"Q&A: streamed answer with {len(sources)} sources")
