"""Profile analytics router.

Aggregates study metrics across all of a user's spaces
into a single response for the dashboard.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import case, cast, Date, func, select

from app.dependencies import CurrentUser, DBSession
from app.models import (
    Document,
    DocumentStatus,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Space,
    StudyPlan,
    StudyTopic,
)
from app.schemas.analytics import (
    ActivityDay,
    DocumentStats,
    ProfileAnalytics,
    QuizScorePoint,
    StudyPlanStats,
    TopicStrengthItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/profile", response_model=ProfileAnalytics)
async def get_profile_analytics(db: DBSession, user: CurrentUser):
    """Get aggregated study analytics for the current user."""

    # ── User's space IDs ──
    space_q = select(Space.id).where(Space.user_id == user.id)
    space_result = db.execute(select(func.count()).select_from(space_q.subquery()))
    spaces_count = space_result.scalar() or 0

    space_ids = db.execute(space_q).scalars().all()

    if not space_ids:
        return ProfileAnalytics(spaces_count=0)

    # ── Document stats ──
    doc_q = select(
        func.count().label("total"),
        func.count().filter(Document.status == DocumentStatus.READY).label("ready"),
        func.count()
        .filter(Document.status == DocumentStatus.PROCESSING)
        .label("processing"),
        func.count().filter(Document.status == DocumentStatus.FAILED).label("failed"),
    ).where(Document.space_id.in_(space_ids))
    doc_row = db.execute(doc_q).one()
    doc_stats = DocumentStats(
        total=doc_row.total,
        ready=doc_row.ready,
        processing=doc_row.processing,
        failed=doc_row.failed,
    )

    # ── Quiz stats ──
    quiz_count_q = select(func.count()).where(Quiz.space_id.in_(space_ids))
    quiz_count = db.execute(quiz_count_q).scalar() or 0

    # Quiz attempts + avg score
    quiz_ids_q = select(Quiz.id).where(Quiz.space_id.in_(space_ids))
    attempt_q = select(
        func.count().label("total"),
    ).where(QuizAttempt.quiz_id.in_(quiz_ids_q))
    attempts_count = db.execute(attempt_q).scalar() or 0

    # Average score across all attempts (grouped by quiz attempt session)
    # Score = (correct / total questions) * 100 per quiz
    avg_score = 0.0
    if attempts_count > 0:
        score_q = select(
            func.avg(case((QuizAttempt.is_correct, 1.0), else_=0.0)).label(
                "avg_correct"
            )
        ).where(QuizAttempt.quiz_id.in_(quiz_ids_q))
        avg_result = db.execute(score_q).scalar()
        avg_score = round((avg_result or 0) * 100, 1)

    # ── Quiz score trend (last 10 quiz sessions) ──
    score_trend: list[QuizScorePoint] = []
    if attempts_count > 0:
        trend_q = (
            select(
                cast(QuizAttempt.attempted_at, Date).label("day"),
                func.avg(case((QuizAttempt.is_correct, 100.0), else_=0.0)).label(
                    "score"
                ),
            )
            .where(QuizAttempt.quiz_id.in_(quiz_ids_q))
            .group_by(cast(QuizAttempt.attempted_at, Date))
            .order_by(cast(QuizAttempt.attempted_at, Date).desc())
            .limit(10)
        )
        trend_rows = db.execute(trend_q).all()
        score_trend = [
            QuizScorePoint(date=str(row.day), score=round(row.score, 1))
            for row in reversed(trend_rows)
        ]

    # ── Topic strengths ──
    topic_strengths: list[TopicStrengthItem] = []
    if quiz_count > 0:
        topic_q = (
            select(
                QuizQuestion.question_text,
                func.count().label("total"),
                func.count().filter(QuizAttempt.is_correct).label("correct"),
            )
            .join(QuizAttempt, QuizAttempt.question_id == QuizQuestion.id)
            .where(QuizQuestion.quiz_id.in_(quiz_ids_q))
            .group_by(QuizQuestion.question_text)
            .having(func.count() >= 1)
            .order_by(func.avg(case((QuizAttempt.is_correct, 1.0), else_=0.0)).asc())
            .limit(8)
        )
        topic_rows = db.execute(topic_q).all()
        topic_strengths = [
            TopicStrengthItem(
                topic=row.question_text[:60],
                accuracy=round((row.correct / row.total) * 100, 1)
                if row.total > 0
                else 0,
                total_questions=row.total,
            )
            for row in topic_rows
        ]

    # ── Study plan stats ──
    plan_q = select(func.count()).where(StudyPlan.space_id.in_(space_ids))
    total_plans = db.execute(plan_q).scalar() or 0

    topic_q = (
        select(
            func.count().label("total"),
            func.count().filter(StudyTopic.completed).label("completed"),
            func.coalesce(func.sum(StudyTopic.estimated_hours), 0.0).label("hours"),
        )
        .join(StudyPlan, StudyTopic.plan_id == StudyPlan.id)
        .where(StudyPlan.space_id.in_(space_ids))
    )
    topic_row = db.execute(topic_q).one()
    study_stats = StudyPlanStats(
        total_plans=total_plans,
        topics_total=topic_row.total,
        topics_completed=topic_row.completed,
        estimated_hours=round(float(topic_row.hours), 1),
    )

    # ── Activity (last 7 days) ──
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    activity_map: dict[str, dict[str, int]] = defaultdict(
        lambda: {"documents": 0, "quizzes": 0, "plans": 0}
    )

    # Pre-fill all 7 days
    for i in range(7):
        day = (week_ago + timedelta(days=i + 1)).date().isoformat()
        activity_map[day]  # trigger default

    # Docs uploaded
    doc_activity = db.execute(
        select(
            cast(Document.created_at, Date).label("day"),
            func.count().label("cnt"),
        )
        .where(Document.space_id.in_(space_ids), Document.created_at >= week_ago)
        .group_by(cast(Document.created_at, Date))
    )
    for row in doc_activity:
        activity_map[str(row.day)]["documents"] = row.cnt

    # Quizzes created
    quiz_activity = db.execute(
        select(
            cast(Quiz.created_at, Date).label("day"),
            func.count().label("cnt"),
        )
        .where(Quiz.space_id.in_(space_ids), Quiz.created_at >= week_ago)
        .group_by(cast(Quiz.created_at, Date))
    )
    for row in quiz_activity:
        activity_map[str(row.day)]["quizzes"] = row.cnt

    # Plans created
    plan_activity = db.execute(
        select(
            cast(StudyPlan.created_at, Date).label("day"),
            func.count().label("cnt"),
        )
        .where(StudyPlan.space_id.in_(space_ids), StudyPlan.created_at >= week_ago)
        .group_by(cast(StudyPlan.created_at, Date))
    )
    for row in plan_activity:
        activity_map[str(row.day)]["plans"] = row.cnt

    activity = [
        ActivityDay(date=day, **counts) for day, counts in sorted(activity_map.items())
    ]

    return ProfileAnalytics(
        spaces_count=spaces_count,
        document_stats=doc_stats,
        quiz_count=quiz_count,
        quiz_attempts_count=attempts_count,
        quiz_avg_score=avg_score,
        quiz_score_trend=score_trend,
        topic_strengths=topic_strengths,
        study_plan_stats=study_stats,
        activity=activity,
    )
