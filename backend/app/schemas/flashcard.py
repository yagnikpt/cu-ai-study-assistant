import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Flashcard Generation ──


class FlashcardGenerateRequest(BaseModel):
    document_id: uuid.UUID | None = Field(
        None, description="Generate from a specific document"
    )
    topic: str | None = Field(
        None, max_length=500, description="Topic to generate flashcards about"
    )
    card_count: int = Field(default=10, ge=1, le=50)


class FlashcardResponse(BaseModel):
    id: uuid.UUID
    card_type: str
    front: str
    back: str
    explanation: str | None
    source_pages: str | None

    model_config = {"from_attributes": True}


class FlashcardDeckResponse(BaseModel):
    id: uuid.UUID
    title: str
    topic: str | None
    document_id: uuid.UUID | None
    card_count: int
    cards: list[FlashcardResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class FlashcardDeckListResponse(BaseModel):
    decks: list[FlashcardDeckResponse]
    total: int


# ── Review ──


class ReviewSubmission(BaseModel):
    flashcard_id: uuid.UUID
    rating: str = Field(description="One of: again, hard, good, easy")


class ReviewRequest(BaseModel):
    reviews: list[ReviewSubmission]


class ReviewResponse(BaseModel):
    deck_id: uuid.UUID
    reviews_recorded: int


# ── Stats ──


class CardStats(BaseModel):
    flashcard_id: uuid.UUID
    front: str
    review_count: int
    last_rating: str | None
    ratings_breakdown: dict[str, int]


class DeckStatsResponse(BaseModel):
    deck_id: uuid.UUID
    title: str
    total_cards: int
    total_reviews: int
    cards_reviewed: int
    cards_not_reviewed: int
    card_stats: list[CardStats]
