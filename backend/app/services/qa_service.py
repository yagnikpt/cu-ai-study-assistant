"""RAG-based Q&A service.

Retrieves relevant document chunks via vector search, constructs a
grounded prompt, and generates answers using Gemini with source citations.
"""

import logging
import uuid

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
4. Be clear, educational, and well-structured in your explanations.
5. Use markdown formatting for readability.
6. Break down complex concepts into simpler parts when helpful.
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
    # Step 1: Embed the question
    query_embedding = await embed_query(question)

    # Step 2: Retrieve relevant chunks
    chunks = await search_similar_chunks(
        db=db,
        query_embedding=query_embedding,
        top_k=top_k,
        document_ids=document_ids,
    )

    # Step 3: Build the prompt
    context = _build_context_prompt(chunks)
    user_prompt = f"""Based on the following source material, answer the student's question.

SOURCE MATERIAL:
{context}

STUDENT'S QUESTION:
{question}

Provide a clear, well-structured answer with source citations."""

    # Step 4: Generate answer with Gemini
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,  # Low temperature for factual accuracy
            max_output_tokens=2048,
        ),
    )

    answer = (
        response.text
        or "I was unable to generate an answer. Please try rephrasing your question."
    )

    # Step 5: Build source references
    sources = []
    for chunk in chunks:
        sources.append(
            {
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
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

    logger.info(f"Q&A: answered question with {len(sources)} sources")

    return {
        "answer": answer,
        "sources": sources,
        "model": settings.generation_model,
    }
