"""Study plan schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StudyPlanGenerateRequest(BaseModel):
    """Request to generate a study plan."""

    document_ids: list[uuid.UUID] | None = Field(
        None, description="Specific documents to base the plan on (or all in space)"
    )
    exam_date: datetime | None = Field(
        None, description="Target exam date for scheduling"
    )
    daily_hours: float = Field(2.0, ge=0.5, le=12.0, description="Hours per day")


class StudyTopicResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    priority: str
    difficulty: str
    estimated_hours: float
    source_pages: str | None
    order_index: int
    completed: bool
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class StudySessionResponse(BaseModel):
    """A computed study session (not stored in DB)."""

    date: str  # ISO date string
    topic_id: uuid.UUID
    topic_title: str
    session_type: str  # "learn" or "review"
    duration_hours: float


class StudyPlanResponse(BaseModel):
    id: uuid.UUID
    title: str
    exam_date: datetime | None
    daily_hours: float
    status: str
    error_message: str | None
    topics: list[StudyTopicResponse]
    schedule: list[StudySessionResponse]
    created_at: datetime
    updated_at: datetime


class StudyPlanListResponse(BaseModel):
    plans: list[StudyPlanResponse]
    total: int


class TopicCompletionUpdate(BaseModel):
    completed: bool
