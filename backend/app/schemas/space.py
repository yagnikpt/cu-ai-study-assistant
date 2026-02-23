"""Space schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SpaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)


class SpaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class SpaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SpaceListResponse(BaseModel):
    spaces: list[SpaceResponse]
    total: int
