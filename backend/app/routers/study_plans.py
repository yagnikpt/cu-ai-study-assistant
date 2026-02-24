"""Study plans router.

Provides AI-powered study plan generation, listing, completion tracking,
and schedule computation — all scoped to a space.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import DBSession
from app.models import Space, StudyPlan, StudyPlanStatus, StudyTopic
from app.schemas.study_plan import (
    StudyPlanGenerateRequest,
    StudyPlanListResponse,
    StudyPlanResponse,
    StudySessionResponse,
    StudyTopicResponse,
    TopicCompletionUpdate,
)
from app.services.study_planner_service import compute_schedule, generate_study_plan

router = APIRouter(prefix="/api/v1/spaces/{space_id}/study-plans", tags=["study-plans"])


def _plan_response(plan: StudyPlan) -> StudyPlanResponse:
    """Build a StudyPlanResponse with computed schedule."""
    topics = [StudyTopicResponse.model_validate(t) for t in plan.topics]
    schedule = compute_schedule(plan.topics, plan.exam_date, plan.daily_hours)

    return StudyPlanResponse(
        id=plan.id,
        title=plan.title,
        exam_date=plan.exam_date,
        daily_hours=plan.daily_hours,
        status=plan.status.value
        if isinstance(plan.status, StudyPlanStatus)
        else plan.status,
        error_message=plan.error_message,
        topics=topics,
        schedule=[StudySessionResponse(**s) for s in schedule],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.post("/generate", response_model=StudyPlanResponse, status_code=201)
async def create_study_plan(
    db: DBSession,
    space_id: uuid.UUID,
    body: StudyPlanGenerateRequest,
):
    """Generate a study plan from space documents using AI."""
    space = await db.get(Space, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    try:
        plan = await generate_study_plan(
            db=db,
            space_id=space_id,
            document_ids=body.document_ids,
            exam_date=body.exam_date,
            daily_hours=body.daily_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Reload with topics
    await db.refresh(plan, ["topics"])
    return _plan_response(plan)


@router.get("/", response_model=StudyPlanListResponse)
async def list_study_plans(db: DBSession, space_id: uuid.UUID):
    """List study plans in a space."""
    query = (
        select(StudyPlan)
        .options(selectinload(StudyPlan.topics))
        .where(StudyPlan.space_id == space_id)
        .order_by(StudyPlan.created_at.desc())
    )
    result = await db.execute(query)
    plans = list(result.scalars().all())

    return StudyPlanListResponse(
        plans=[_plan_response(p) for p in plans],
        total=len(plans),
    )


@router.get("/{plan_id}", response_model=StudyPlanResponse)
async def get_study_plan(db: DBSession, space_id: uuid.UUID, plan_id: uuid.UUID):
    """Get a study plan with topics and computed schedule."""
    query = (
        select(StudyPlan)
        .options(selectinload(StudyPlan.topics))
        .where(StudyPlan.id == plan_id, StudyPlan.space_id == space_id)
    )
    result = await db.execute(query)
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Study plan not found")

    return _plan_response(plan)


@router.patch("/{plan_id}/topics/{topic_id}", response_model=StudyTopicResponse)
async def toggle_topic_completion(
    db: DBSession,
    space_id: uuid.UUID,
    plan_id: uuid.UUID,
    topic_id: uuid.UUID,
    body: TopicCompletionUpdate,
):
    """Toggle a topic's completion status."""
    # Verify plan belongs to space
    plan = await db.get(StudyPlan, plan_id)
    if not plan or plan.space_id != space_id:
        raise HTTPException(status_code=404, detail="Study plan not found")

    topic = await db.get(StudyTopic, topic_id)
    if not topic or topic.plan_id != plan_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic.completed = body.completed
    topic.completed_at = datetime.now(timezone.utc) if body.completed else None

    await db.flush()
    await db.refresh(topic)
    return StudyTopicResponse.model_validate(topic)


@router.delete("/{plan_id}", status_code=204)
async def delete_study_plan(db: DBSession, space_id: uuid.UUID, plan_id: uuid.UUID):
    """Delete a study plan and all its topics."""
    plan = await db.get(StudyPlan, plan_id)
    if not plan or plan.space_id != space_id:
        raise HTTPException(status_code=404, detail="Study plan not found")

    await db.delete(plan)
    await db.flush()
