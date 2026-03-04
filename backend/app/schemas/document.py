import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Tag Schemas ──


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str | None = Field(
        None, pattern=r"^#[0-9a-fA-F]{6}$", description="Hex color code, e.g. #FF5733"
    )


class TagResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None
    space_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Document Schemas ──


class DocumentUploadMeta(BaseModel):
    """Optional metadata sent alongside file upload."""

    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class DocumentUpdate(BaseModel):
    pass


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content: str
    page_start: int
    page_end: int
    section_title: str | None
    token_count: int

    model_config = {"from_attributes": True}


class DocumentImageResponse(BaseModel):
    id: uuid.UUID
    gcs_url: str
    page_number: int | None
    image_index: int
    mime_type: str
    caption: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size_bytes: int
    page_count: int
    status: str
    error_message: str | None
    chunk_count: int = 0
    image_count: int = 0
    tags: list[TagResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class DocumentTagsUpdate(BaseModel):
    tag_ids: list[uuid.UUID]
