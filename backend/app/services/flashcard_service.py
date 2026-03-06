"""Flashcard deck generation and review service.

Generates flashcard decks from course material using Gemini AI,
records self-ratings, and provides study stats.
"""

import json
import logging
import uuid

from google import genai

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Document,
    DocumentChunk,
    Flashcard,
    FlashcardDeck,
    FlashcardReview,
    FlashcardType,
    ReviewRating,
)
from app.services.embeddings import embed_query
from app.services.genai_client import get_genai_client
from app.services.vector_search import search_similar_chunks

logger = logging.getLogger(__name__)

FLASHCARD_SYSTEM_PROMPT = """You are an AI study assistant that generates flashcards from educational material.

You MUST respond with valid JSON only - no markdown, no code fences, no extra text.

Rules:
1. Generate flashcards ONLY from the provided source material.
2. Each flashcard must be clearly answerable from the source text.
3. For each card, decide the best format:
   - "term_definition": front is a term/concept, back is its definition/explanation.
   - "question_answer": front is a question, back is a concise answer.
4. The 'front' should be concise and clear.
5. The 'back' should be accurate and complete but not overly long.
6. Include a brief 'explanation' that adds context or a memory aid.
7. Include source page numbers for each card.
8. Vary between term_definition and question_answer to keep studying engaging.
9. Cover the most important concepts from the material.

Output ONLY valid JSON matching this exact schema:
{
  "cards": [
    {
      "card_type": "term_definition",
      "front": "Term or concept",
      "back": "Definition or explanation",
      "explanation": "Additional context or memory aid [Source: doc, p.X]",
      "source_pages": "p.5"
    },
    {
      "card_type": "question_answer",
      "front": "What is...?",
      "back": "The answer is...",
      "explanation": "This is important because... [Source: doc, p.X]",
      "source_pages": "pp.3-4"
    }
  ]
}
"""


async def generate_flashcard_deck(
    db: AsyncSession,
    document_id: uuid.UUID | None = None,
    topic: str | None = None,
    card_count: int = 10,
    space_id: uuid.UUID | None = None,
) -> FlashcardDeck:
    """Generate a flashcard deck from course materials.

    Args:
        db: Async database session.
        document_id: Generate from a specific document.
        topic: Topic to generate flashcards about.
        card_count: Number of cards to generate.
        space_id: Scope to a specific space.

    Returns:
        FlashcardDeck ORM object with cards populated.
    """
    # Retrieve relevant chunks
    chunks: list[dict] = []
    effective_topic = topic or "General"

    if topic:
        query_embedding = await embed_query(topic)
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
    elif document_id:
        query = (
            select(DocumentChunk, Document.original_filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(DocumentChunk.chunk_index)
            .limit(15)
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

        # Derive topic from document
        doc = await db.get(Document, document_id)
        if doc:
            effective_topic = doc.original_filename.rsplit(".", 1)[0]

    if not chunks:
        raise ValueError("No source material found to generate flashcards from.")

    # Build context
    context_parts = []
    chunk_id_map: dict[int, uuid.UUID] = {}
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
        chunk_id_map[i] = chunk["chunk_id"]

    context = "\n\n---\n\n".join(context_parts)

    user_prompt = f"""Generate exactly {card_count} flashcards from this material about: {effective_topic}

SOURCE MATERIAL:
{context}

Generate the flashcards as JSON."""

    # Generate with Gemini
    client = get_genai_client()
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=FLASHCARD_SYSTEM_PROMPT,
            temperature=0.5,
            max_output_tokens=4096,
        ),
    )

    raw_text = response.text or ""

    # Clean up potential markdown code fences
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1])

    try:
        deck_data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse flashcard JSON: {e}\nRaw: {raw_text[:500]}")
        raise ValueError(
            "Failed to generate valid flashcards. Please try again."
        ) from e

    # Create FlashcardDeck record
    deck = FlashcardDeck(
        title=f"Flashcards: {effective_topic}",
        document_id=document_id,
        space_id=space_id,
        topic=effective_topic,
        card_count=len(deck_data.get("cards", [])),
    )
    db.add(deck)
    await db.flush()

    # Create Flashcard records
    for c_data in deck_data.get("cards", []):
        card_type = (
            FlashcardType.TERM_DEFINITION
            if c_data.get("card_type") == "term_definition"
            else FlashcardType.QUESTION_ANSWER
        )

        card = Flashcard(
            deck_id=deck.id,
            card_type=card_type,
            front=c_data["front"],
            back=c_data["back"],
            explanation=c_data.get("explanation"),
            source_chunk_ids=[str(cid) for cid in chunk_id_map.values()],
            source_pages=c_data.get("source_pages"),
        )
        db.add(card)

    await db.flush()

    logger.info(f"Generated flashcard deck '{deck.title}' with {deck.card_count} cards")
    return deck


async def record_reviews(
    db: AsyncSession,
    deck_id: uuid.UUID,
    reviews: list[dict],
) -> int:
    """Record self-rating reviews for flashcards.

    Args:
        db: Async database session.
        deck_id: The deck being studied.
        reviews: List of {flashcard_id, rating} dicts.

    Returns:
        Number of reviews recorded.
    """
    rating_map = {
        "again": ReviewRating.AGAIN,
        "hard": ReviewRating.HARD,
        "good": ReviewRating.GOOD,
        "easy": ReviewRating.EASY,
    }

    count = 0
    for rev in reviews:
        flashcard_id = rev["flashcard_id"]
        if isinstance(flashcard_id, str):
            flashcard_id = uuid.UUID(flashcard_id)

        rating_str = rev["rating"].lower()
        rating = rating_map.get(rating_str)
        if not rating:
            logger.warning(f"Invalid rating '{rev['rating']}' for card {flashcard_id}")
            continue

        review = FlashcardReview(
            deck_id=deck_id,
            flashcard_id=flashcard_id,
            rating=rating,
        )
        db.add(review)
        count += 1

    await db.flush()
    logger.info(f"Recorded {count} reviews for deck {deck_id}")
    return count


async def get_deck_stats(
    db: AsyncSession,
    deck_id: uuid.UUID,
) -> dict:
    """Get study statistics for a flashcard deck.

    Args:
        db: Async database session.
        deck_id: The deck to get stats for.

    Returns:
        Stats dict with per-card review breakdowns.
    """
    deck = await db.get(FlashcardDeck, deck_id)
    if not deck:
        raise ValueError(f"Deck {deck_id} not found")

    # Get all cards for this deck
    cards_result = await db.execute(
        select(Flashcard).where(Flashcard.deck_id == deck_id)
    )
    cards = cards_result.scalars().all()

    # Get all reviews for this deck
    reviews_result = await db.execute(
        select(FlashcardReview)
        .where(FlashcardReview.deck_id == deck_id)
        .order_by(FlashcardReview.reviewed_at)
    )
    reviews = reviews_result.scalars().all()

    # Build per-card stats
    card_review_map: dict[uuid.UUID, list[FlashcardReview]] = {}
    for review in reviews:
        card_review_map.setdefault(review.flashcard_id, []).append(review)

    card_stats = []
    cards_reviewed = 0
    for card in cards:
        card_reviews = card_review_map.get(card.id, [])
        ratings_breakdown: dict[str, int] = {
            "again": 0,
            "hard": 0,
            "good": 0,
            "easy": 0,
        }
        for r in card_reviews:
            ratings_breakdown[r.rating.value] += 1

        last_rating = card_reviews[-1].rating.value if card_reviews else None

        if card_reviews:
            cards_reviewed += 1

        card_stats.append(
            {
                "flashcard_id": card.id,
                "front": card.front,
                "review_count": len(card_reviews),
                "last_rating": last_rating,
                "ratings_breakdown": ratings_breakdown,
            }
        )

    return {
        "deck_id": deck_id,
        "title": deck.title,
        "total_cards": len(cards),
        "total_reviews": len(reviews),
        "cards_reviewed": cards_reviewed,
        "cards_not_reviewed": len(cards) - cards_reviewed,
        "card_stats": card_stats,
    }
