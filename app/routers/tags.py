"""Tag management router."""

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import DBSession
from app.models import Tag
from app.schemas.document import TagCreate, TagResponse

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


@router.post("/", response_model=TagResponse, status_code=201)
async def create_tag(db: DBSession, body: TagCreate):
    """Create a new tag for organizing documents."""
    # Check uniqueness
    existing = await db.execute(select(Tag).where(Tag.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Tag '{body.name}' already exists")

    tag = Tag(name=body.name, color=body.color)
    db.add(tag)
    await db.flush()

    return TagResponse.model_validate(tag)


@router.get("/", response_model=list[TagResponse])
async def list_tags(db: DBSession):
    """List all tags."""
    result = await db.execute(select(Tag).order_by(Tag.name))
    tags = result.scalars().all()
    return [TagResponse.model_validate(t) for t in tags]


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(db: DBSession, tag_id: uuid.UUID):
    """Delete a tag. Does not delete associated documents."""
    tag = await db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    await db.delete(tag)
