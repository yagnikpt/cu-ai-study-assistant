"""Flashcard deck generation and management router."""

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.dependencies import DBSession
from app.models import Document, FlashcardDeck, Flashcard, Space
from app.schemas.flashcard import (
    CardStats,
    DeckStatsResponse,
    FlashcardDeckListResponse,
    FlashcardDeckResponse,
    FlashcardGenerateRequest,
    FlashcardResponse,
    ReviewRequest,
    ReviewResponse,
)
from app.services.flashcard_service import (
    generate_flashcard_deck,
    get_deck_stats,
    record_reviews,
)

router = APIRouter(prefix="/api/v1/spaces/{space_id}/flashcards", tags=["flashcards"])


@router.post("/generate", response_model=FlashcardDeckResponse, status_code=201)
async def create_flashcard_deck(
    db: DBSession, space_id: uuid.UUID, body: FlashcardGenerateRequest
):
    """Generate a flashcard deck from course materials in this space.

    Provide either:
    - `document_id`: Generate from a specific document
    - `topic`: Generate flashcards about a topic (searches space docs)
    - Both: Generate topic-specific flashcards from a specific document
    """
    if not body.document_id and not body.topic:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'document_id' or 'topic' (or both).",
        )

    # Validate space exists
    space = await db.get(Space, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    # Validate document belongs to space if provided
    if body.document_id:
        doc = await db.get(Document, body.document_id)
        if not doc or doc.space_id != space_id:
            raise HTTPException(
                status_code=400,
                detail="The specified document does not belong to this space.",
            )

    try:
        deck = await generate_flashcard_deck(
            db=db,
            document_id=body.document_id,
            topic=body.topic,
            card_count=body.card_count,
            space_id=space_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Flashcard generation failed: {e}"
        ) from e

    # Re-fetch with cards
    result = await db.execute(
        select(FlashcardDeck)
        .options(selectinload(FlashcardDeck.cards))
        .where(FlashcardDeck.id == deck.id)
    )
    deck = result.scalar_one()

    return FlashcardDeckResponse(
        id=deck.id,
        title=deck.title,
        topic=deck.topic,
        document_id=deck.document_id,
        card_count=deck.card_count,
        cards=[
            FlashcardResponse(
                id=c.id,
                card_type=c.card_type.value,
                front=c.front,
                back=c.back,
                explanation=c.explanation,
                source_pages=c.source_pages,
            )
            for c in deck.cards
        ],
        created_at=deck.created_at,
    )


@router.get("/", response_model=FlashcardDeckListResponse)
async def list_flashcard_decks(
    db: DBSession,
    space_id: uuid.UUID,
    document_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List flashcard decks in this space."""
    query = (
        select(FlashcardDeck)
        .options(selectinload(FlashcardDeck.cards))
        .where(FlashcardDeck.space_id == space_id)
    )

    if document_id:
        query = query.where(FlashcardDeck.document_id == document_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    query = query.order_by(FlashcardDeck.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    decks = result.scalars().all()

    return FlashcardDeckListResponse(
        decks=[
            FlashcardDeckResponse(
                id=d.id,
                title=d.title,
                topic=d.topic,
                document_id=d.document_id,
                card_count=d.card_count,
                cards=[
                    FlashcardResponse(
                        id=c.id,
                        card_type=c.card_type.value,
                        front=c.front,
                        back=c.back,
                        explanation=c.explanation,
                        source_pages=c.source_pages,
                    )
                    for c in d.cards
                ],
                created_at=d.created_at,
            )
            for d in decks
        ],
        total=total,
    )


@router.get("/{deck_id}", response_model=FlashcardDeckResponse)
async def get_flashcard_deck(db: DBSession, space_id: uuid.UUID, deck_id: uuid.UUID):
    """Get a flashcard deck with all its cards."""
    result = await db.execute(
        select(FlashcardDeck)
        .options(selectinload(FlashcardDeck.cards))
        .where(FlashcardDeck.id == deck_id)
    )
    deck = result.scalar_one_or_none()
    if not deck or deck.space_id != space_id:
        raise HTTPException(status_code=404, detail="Deck not found in this space")

    return FlashcardDeckResponse(
        id=deck.id,
        title=deck.title,
        topic=deck.topic,
        document_id=deck.document_id,
        card_count=deck.card_count,
        cards=[
            FlashcardResponse(
                id=c.id,
                card_type=c.card_type.value,
                front=c.front,
                back=c.back,
                explanation=c.explanation,
                source_pages=c.source_pages,
            )
            for c in deck.cards
        ],
        created_at=deck.created_at,
    )


@router.post("/{deck_id}/review", response_model=ReviewResponse)
async def submit_reviews(
    db: DBSession, space_id: uuid.UUID, deck_id: uuid.UUID, body: ReviewRequest
):
    """Submit self-rating reviews for flashcards in a deck.

    Ratings: again, hard, good, easy
    """
    # Validate deck belongs to space
    deck = await db.get(FlashcardDeck, deck_id)
    if not deck or deck.space_id != space_id:
        raise HTTPException(status_code=404, detail="Deck not found in this space")

    try:
        count = await record_reviews(
            db=db,
            deck_id=deck_id,
            reviews=[r.model_dump() for r in body.reviews],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ReviewResponse(deck_id=deck_id, reviews_recorded=count)


@router.get("/{deck_id}/stats", response_model=DeckStatsResponse)
async def get_stats(db: DBSession, space_id: uuid.UUID, deck_id: uuid.UUID):
    """Get study statistics for a flashcard deck.

    Shows per-card review counts and rating breakdowns.
    """
    # Validate deck belongs to space
    deck = await db.get(FlashcardDeck, deck_id)
    if not deck or deck.space_id != space_id:
        raise HTTPException(status_code=404, detail="Deck not found in this space")

    try:
        result = await get_deck_stats(db=db, deck_id=deck_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return DeckStatsResponse(
        deck_id=result["deck_id"],
        title=result["title"],
        total_cards=result["total_cards"],
        total_reviews=result["total_reviews"],
        cards_reviewed=result["cards_reviewed"],
        cards_not_reviewed=result["cards_not_reviewed"],
        card_stats=[CardStats(**cs) for cs in result["card_stats"]],
    )


@router.delete("/{deck_id}", status_code=204)
async def delete_flashcard_deck(db: DBSession, space_id: uuid.UUID, deck_id: uuid.UUID):
    """Delete a flashcard deck and all its cards and reviews."""
    deck = await db.get(FlashcardDeck, deck_id)
    if not deck or deck.space_id != space_id:
        raise HTTPException(status_code=404, detail="Deck not found in this space")

    await db.delete(deck)
    await db.flush()
