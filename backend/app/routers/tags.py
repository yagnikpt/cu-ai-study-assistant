"""Tag management router — scoped to spaces."""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.models import Space, Tag
from app.schemas.document import TagCreate, TagResponse

router = APIRouter(prefix="/api/v1/spaces/{space_id}/tags", tags=["tags"])


@router.post("/", response_model=TagResponse, status_code=201)
async def create_tag(db: DBSession, space_id: uuid.UUID, body: TagCreate):
    """Create a new tag within a space."""
    # Validate space exists
    space = await db.get(Space, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    # Check uniqueness within the space
    existing = await db.execute(
        select(Tag).where(Tag.name == body.name, Tag.space_id == space_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Tag '{body.name}' already exists in this space",
        )

    tag = Tag(name=body.name, color=body.color, space_id=space_id)
    db.add(tag)
    await db.flush()

    return TagResponse.model_validate(tag)


@router.get("/", response_model=list[TagResponse])
async def list_tags(db: DBSession, space_id: uuid.UUID):
    """List all tags in a space."""
    result = await db.execute(
        select(Tag).where(Tag.space_id == space_id).order_by(Tag.name)
    )
    tags = result.scalars().all()
    return [TagResponse.model_validate(t) for t in tags]


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(db: DBSession, space_id: uuid.UUID, tag_id: uuid.UUID):
    """Delete a tag. Does not delete associated documents."""
    tag = await db.get(Tag, tag_id)
    if not tag or tag.space_id != space_id:
        raise HTTPException(status_code=404, detail="Tag not found")

    await db.delete(tag)
