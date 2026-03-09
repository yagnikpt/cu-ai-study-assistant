"""Spaces management router.

Provides CRUD for study spaces that group documents and derived content.
All operations are scoped to the authenticated user.
"""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DBSession
from app.models import Document, Space
from app.schemas.space import SpaceCreate, SpaceListResponse, SpaceResponse, SpaceUpdate

router = APIRouter(prefix="/api/v1/spaces", tags=["spaces"])


@router.post("/", response_model=SpaceResponse, status_code=201)
async def create_space(db: DBSession, user: CurrentUser, body: SpaceCreate):
    """Create a new study space."""
    space = Space(name=body.name, description=body.description, user_id=user.id)
    db.add(space)
    db.flush()
    db.refresh(space)
    return SpaceResponse(
        id=space.id,
        name=space.name,
        description=space.description,
        document_count=0,
        created_at=space.created_at,
        updated_at=space.updated_at,
    )


@router.get("/", response_model=SpaceListResponse)
async def list_spaces(db: DBSession, user: CurrentUser):
    """List study spaces owned by the current user."""
    # Sub-query for document counts
    doc_count_sq = (
        select(
            Document.space_id,
            func.count(Document.id).label("doc_count"),
        )
        .group_by(Document.space_id)
        .subquery()
    )

    query = (
        select(Space, func.coalesce(doc_count_sq.c.doc_count, 0).label("doc_count"))
        .outerjoin(doc_count_sq, Space.id == doc_count_sq.c.space_id)
        .where(Space.user_id == user.id)
        .order_by(Space.updated_at.desc())
    )

    result = db.execute(query)
    rows = result.all()

    total_q = select(func.count()).select_from(Space).where(Space.user_id == user.id)
    total = db.scalar(total_q) or 0

    return SpaceListResponse(
        spaces=[
            SpaceResponse(
                id=space.id,
                name=space.name,
                description=space.description,
                document_count=doc_count,
                created_at=space.created_at,
                updated_at=space.updated_at,
            )
            for space, doc_count in rows
        ],
        total=total,
    )


@router.get("/{space_id}", response_model=SpaceResponse)
async def get_space(db: DBSession, user: CurrentUser, space_id: uuid.UUID):
    """Get a single space with its document count."""
    space = db.get(Space, space_id)
    if not space or space.user_id != user.id:
        raise HTTPException(status_code=404, detail="Space not found")

    doc_count = db.scalar(
        select(func.count()).select_from(Document).where(Document.space_id == space_id)
    )

    return SpaceResponse(
        id=space.id,
        name=space.name,
        description=space.description,
        document_count=doc_count or 0,
        created_at=space.created_at,
        updated_at=space.updated_at,
    )


@router.patch("/{space_id}", response_model=SpaceResponse)
async def update_space(
    db: DBSession, user: CurrentUser, space_id: uuid.UUID, body: SpaceUpdate
):
    """Update space metadata."""
    space = db.get(Space, space_id)
    if not space or space.user_id != user.id:
        raise HTTPException(status_code=404, detail="Space not found")

    if body.name is not None:
        space.name = body.name
    if body.description is not None:
        space.description = body.description

    db.flush()
    db.refresh(space)

    doc_count = db.scalar(
        select(func.count()).select_from(Document).where(Document.space_id == space_id)
    )

    return SpaceResponse(
        id=space.id,
        name=space.name,
        description=space.description,
        document_count=doc_count or 0,
        created_at=space.created_at,
        updated_at=space.updated_at,
    )


@router.delete("/{space_id}", status_code=204)
async def delete_space(db: DBSession, user: CurrentUser, space_id: uuid.UUID):
    """Delete a space and all its documents, quizzes, chunks, and embeddings."""
    space = db.get(Space, space_id)
    if not space or space.user_id != user.id:
        raise HTTPException(status_code=404, detail="Space not found")

    db.delete(space)
    db.flush()
