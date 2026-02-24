"""Study plan generation and scheduling service.

Uses Gemini to analyze document chunks and generate structured study plans
with topic breakdowns, difficulty ratings, and time estimates.
Computes spaced repetition schedules algorithmically.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Document,
    DocumentChunk,
    StudyPlan,
    StudyPlanStatus,
    StudyTopic,
    TopicDifficulty,
    TopicPriority,
)

logger = logging.getLogger(__name__)

PLAN_PROMPT = """\
You are an expert study coach. Analyze the following course material and create
a structured study plan.

For each major topic in the material, provide:
1. A clear topic title
2. A brief description of what to study
3. Priority level (high, medium, low) based on importance and exam likelihood
4. Difficulty level (hard, medium, easy) based on conceptual complexity
5. Estimated study hours needed to master the topic
6. Source page references

Order topics by recommended study sequence (prerequisites first, then build up).

Output ONLY valid JSON matching this exact schema:
{
  "title": "Study Plan for [Course/Subject]",
  "topics": [
    {
      "title": "Topic Name",
      "description": "What to study and key concepts to master",
      "priority": "high|medium|low",
      "difficulty": "hard|medium|easy",
      "estimated_hours": 2.5,
      "source_pages": "doc1 pp.3-5, doc2 pp.12-15"
    }
  ]
}

MATERIAL:
"""


async def generate_study_plan(
    db: AsyncSession,
    space_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None = None,
    exam_date: datetime | None = None,
    daily_hours: float = 2.0,
) -> StudyPlan:
    """Generate a study plan from course materials using Gemini.

    Args:
        db: Async database session.
        space_id: Space containing the documents.
        document_ids: Specific documents to use (or all ready docs in space).
        exam_date: Target exam date for scheduling.
        daily_hours: Study hours per day.

    Returns:
        StudyPlan ORM object with topics populated.
    """
    # Step 1: Gather document chunks
    if document_ids:
        doc_ids = document_ids
    else:
        result = await db.execute(
            select(Document.id).where(
                Document.space_id == space_id,
                Document.status == "ready",
            )
        )
        doc_ids = list(result.scalars().all())

    if not doc_ids:
        raise ValueError("No ready documents found in this space")

    # Get a broad sample of chunks for comprehensive topic analysis
    query = (
        select(DocumentChunk, Document.original_filename)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.document_id.in_(doc_ids))
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        .limit(30)  # generous limit for good topic coverage
    )
    result = await db.execute(query)
    rows = result.all()

    if not rows:
        raise ValueError("No indexed content found in the selected documents")

    # Build context for Gemini
    context_parts = []
    for chunk, filename in rows:
        pages = f"pp.{chunk.page_start}-{chunk.page_end}" if chunk.page_start else ""
        context_parts.append(f"[{filename} {pages}]\n{chunk.content}")

    context = "\n\n---\n\n".join(context_parts)

    # Step 2: Call Gemini
    client = genai.Client(api_key=settings.gemini_api_key)
    response = await client.aio.models.generate_content(
        model=settings.generation_model,
        contents=PLAN_PROMPT + context,
        config=genai.types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=4000,
        ),
    )

    raw = response.text or ""

    # Strip markdown fences if present
    if "```json" in raw:
        raw = raw.split("```json", 1)[1]
    if "```" in raw:
        raw = raw.split("```", 1)[0]

    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Gemini response as JSON: {e}")

    # Step 3: Create StudyPlan + StudyTopic records
    plan = StudyPlan(
        space_id=space_id,
        title=data.get("title", "Study Plan"),
        exam_date=exam_date,
        daily_hours=daily_hours,
        status=StudyPlanStatus.READY,
    )
    db.add(plan)
    await db.flush()

    for idx, topic_data in enumerate(data.get("topics", [])):
        priority_str = topic_data.get("priority", "medium").lower()
        difficulty_str = topic_data.get("difficulty", "medium").lower()

        try:
            priority = TopicPriority(priority_str)
        except ValueError:
            priority = TopicPriority.MEDIUM

        try:
            difficulty = TopicDifficulty(difficulty_str)
        except ValueError:
            difficulty = TopicDifficulty.MEDIUM

        topic = StudyTopic(
            plan_id=plan.id,
            title=topic_data.get("title", f"Topic {idx + 1}"),
            description=topic_data.get("description", ""),
            priority=priority,
            difficulty=difficulty,
            estimated_hours=float(topic_data.get("estimated_hours", 1.0)),
            source_pages=topic_data.get("source_pages"),
            order_index=idx,
        )
        db.add(topic)

    await db.flush()
    await db.refresh(plan)
    return plan


def compute_schedule(
    topics: list[StudyTopic],
    exam_date: datetime | None,
    daily_hours: float,
) -> list[dict]:
    """Compute a spaced repetition study schedule.

    Distributes topics across days with review sessions:
    - Hard topics: 3 sessions (learn + 2 reviews)
    - Medium topics: 2 sessions (learn + 1 review)
    - Easy topics: 1 session (learn only)

    Args:
        topics: List of StudyTopic objects.
        exam_date: Target exam date (or None for open-ended).
        daily_hours: Available study hours per day.

    Returns:
        List of session dicts: {date, topic_id, topic_title, session_type, duration_hours}
    """
    if not topics:
        return []

    # Build session list: each topic gets learn + reviews
    sessions = []
    for topic in topics:
        # Learning session
        sessions.append(
            {
                "topic_id": str(topic.id),
                "topic_title": topic.title,
                "session_type": "learn",
                "duration_hours": topic.estimated_hours,
                "priority_weight": _priority_weight(topic.priority),
                "difficulty": topic.difficulty,
            }
        )

        # Review sessions based on difficulty
        review_count = {"hard": 2, "medium": 1, "easy": 0}.get(
            topic.difficulty.value, 1
        )
        review_duration = topic.estimated_hours * 0.4  # reviews are shorter

        for _ in range(review_count):
            sessions.append(
                {
                    "topic_id": str(topic.id),
                    "topic_title": topic.title,
                    "session_type": "review",
                    "duration_hours": round(review_duration, 1),
                    "priority_weight": _priority_weight(topic.priority),
                    "difficulty": topic.difficulty,
                }
            )

    # Distribute sessions across days
    start_date = datetime.now(timezone.utc).date() + timedelta(days=1)  # start tomorrow

    if exam_date:
        end_date = exam_date.date() if hasattr(exam_date, "date") else exam_date
        total_days = max((end_date - start_date).days, 1)
    else:
        # Estimate days needed
        total_hours = sum(s["duration_hours"] for s in sessions)
        total_days = max(int(total_hours / daily_hours) + 1, 1)

    # Sort: learn sessions first (by order), then reviews
    learn_sessions = [s for s in sessions if s["session_type"] == "learn"]
    review_sessions = [s for s in sessions if s["session_type"] == "review"]

    # Pack sessions into days
    schedule = []
    current_day = 0
    day_remaining = daily_hours

    for session in learn_sessions:
        date = start_date + timedelta(days=current_day)
        if day_remaining < session["duration_hours"] and day_remaining < daily_hours:
            current_day += 1
            day_remaining = daily_hours
            date = start_date + timedelta(days=current_day)

        schedule.append(
            {
                "date": date.isoformat(),
                "topic_id": session["topic_id"],
                "topic_title": session["topic_title"],
                "session_type": "learn",
                "duration_hours": session["duration_hours"],
            }
        )
        day_remaining -= session["duration_hours"]
        if day_remaining <= 0:
            current_day += 1
            day_remaining = daily_hours

    # Space reviews across remaining days
    if review_sessions:
        review_start = current_day + 1  # gap after learning
        for i, session in enumerate(review_sessions):
            day = review_start + i
            if day >= total_days:
                day = total_days - 1  # compress into final days
            date = start_date + timedelta(days=day)

            schedule.append(
                {
                    "date": date.isoformat(),
                    "topic_id": session["topic_id"],
                    "topic_title": session["topic_title"],
                    "session_type": "review",
                    "duration_hours": session["duration_hours"],
                }
            )

    # Sort by date
    schedule.sort(key=lambda s: s["date"])
    return schedule


def _priority_weight(priority: TopicPriority) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(priority.value, 2)
