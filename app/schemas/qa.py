import uuid

from pydantic import BaseModel, Field


# ── Q&A Schemas ──


class SourceReference(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_start: int
    page_end: int
    section_title: str | None
    relevance_score: float
    text_preview: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    document_ids: list[uuid.UUID] | None = Field(
        None,
        description="Limit search to specific documents. If empty, searches all documents.",
    )
    top_k: int = Field(
        default=5, ge=1, le=20, description="Number of chunks to retrieve"
    )


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    model: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    document_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    content: str
    page_start: int
    page_end: int
    section_title: str | None
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
