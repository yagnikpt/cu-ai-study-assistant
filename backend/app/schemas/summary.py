import uuid

from pydantic import BaseModel, Field


class SummaryRequest(BaseModel):
    topic: str | None = Field(None, max_length=500, description="Topic to summarize")
    document_id: uuid.UUID | None = Field(
        None, description="Document to summarize from"
    )
    page_start: int | None = Field(None, ge=1, description="Start page (inclusive)")
    page_end: int | None = Field(None, ge=1, description="End page (inclusive)")
    detail_level: str = Field(
        default="standard",
        pattern=r"^(brief|standard|detailed)$",
        description="Level of detail: brief, standard, or detailed",
    )


class SummarySource(BaseModel):
    document_name: str
    pages: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID


class SummaryImageReference(BaseModel):
    image_id: str
    image_url: str
    document_id: str
    document_name: str
    page_number: int | None = None
    caption: str | None = None
    relevance_score: float


class SummaryResponse(BaseModel):
    summary: str  # Markdown-formatted summary
    topic: str
    sources: list[SummarySource]
    images: list[SummaryImageReference] = []
    model: str
