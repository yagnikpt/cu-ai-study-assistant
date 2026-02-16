"""Quiz generation and management router."""

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.dependencies import DBSession
from app.models import Quiz, QuizQuestion
from app.schemas.quiz import (
    QuizAttemptRequest,
    QuizAttemptResponse,
    QuizGenerateRequest,
    QuizListResponse,
    QuizQuestionResponse,
    QuizQuestionWithAnswer,
    QuizResponse,
    QuizResultsResponse,
    QuestionFeedback,
    TopicStrength,
)
from app.services.quiz_service import generate_quiz, grade_attempt, get_quiz_results

router = APIRouter(prefix="/api/v1/quizzes", tags=["quizzes"])


@router.post("/generate", response_model=QuizResponse, status_code=201)
async def create_quiz(db: DBSession, body: QuizGenerateRequest):
    """Generate a quiz from course materials.

    Provide either:
    - `document_id`: Generate from a specific document
    - `topic`: Generate questions about a topic (searches all docs)
    - Both: Generate topic-specific questions from a specific document

    Questions are mapped back to source material with page references.
    """
    if not body.document_id and not body.topic:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'document_id' or 'topic' (or both).",
        )

    try:
        quiz = await generate_quiz(
            db=db,
            document_id=body.document_id,
            topic=body.topic,
            question_count=body.question_count,
            question_types=body.question_types,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Quiz generation failed: {e}"
        ) from e

    # Re-fetch with questions
    result = await db.execute(
        select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz.id)
    )
    quiz = result.scalar_one()

    return QuizResponse(
        id=quiz.id,
        title=quiz.title,
        topic=quiz.topic,
        document_id=quiz.document_id,
        question_count=quiz.question_count,
        questions=[
            QuizQuestionResponse(
                id=q.id,
                question_type=q.question_type.value,
                question_text=q.question_text,
                options=q.options,
                source_pages=q.source_pages,
            )
            for q in quiz.questions
        ],
        created_at=quiz.created_at,
    )


@router.get("/", response_model=QuizListResponse)
async def list_quizzes(
    db: DBSession,
    document_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List all generated quizzes."""
    query = select(Quiz).options(selectinload(Quiz.questions))

    if document_id:
        query = query.where(Quiz.document_id == document_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    query = query.order_by(Quiz.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    quizzes = result.scalars().all()

    return QuizListResponse(
        quizzes=[
            QuizResponse(
                id=q.id,
                title=q.title,
                topic=q.topic,
                document_id=q.document_id,
                question_count=q.question_count,
                questions=[
                    QuizQuestionResponse(
                        id=qq.id,
                        question_type=qq.question_type.value,
                        question_text=qq.question_text,
                        options=qq.options,
                        source_pages=qq.source_pages,
                    )
                    for qq in q.questions
                ],
                created_at=q.created_at,
            )
            for q in quizzes
        ],
        total=total,
    )


@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(db: DBSession, quiz_id: uuid.UUID):
    """Get a quiz with its questions (without answers - for taking the quiz)."""
    result = await db.execute(
        select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    return QuizResponse(
        id=quiz.id,
        title=quiz.title,
        topic=quiz.topic,
        document_id=quiz.document_id,
        question_count=quiz.question_count,
        questions=[
            QuizQuestionResponse(
                id=q.id,
                question_type=q.question_type.value,
                question_text=q.question_text,
                options=q.options,
                source_pages=q.source_pages,
            )
            for q in quiz.questions
        ],
        created_at=quiz.created_at,
    )


@router.post("/{quiz_id}/attempt", response_model=QuizAttemptResponse)
async def submit_attempt(db: DBSession, quiz_id: uuid.UUID, body: QuizAttemptRequest):
    """Submit answers for a quiz and get graded feedback.

    Each answer includes:
    - Whether it was correct
    - The correct answer
    - An explanation with source references
    """
    try:
        result = await grade_attempt(
            db=db,
            quiz_id=quiz_id,
            answers=[a.model_dump() for a in body.answers],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return QuizAttemptResponse(
        quiz_id=result["quiz_id"],
        total_questions=result["total_questions"],
        correct_count=result["correct_count"],
        score_percentage=result["score_percentage"],
        feedback=[QuestionFeedback(**f) for f in result["feedback"]],
    )


@router.get("/{quiz_id}/results", response_model=QuizResultsResponse)
async def get_results(db: DBSession, quiz_id: uuid.UUID):
    """Get aggregated results for a quiz including topic strength analysis.

    Shows which topics need reinforcement based on past attempts.
    """
    try:
        result = await get_quiz_results(db=db, quiz_id=quiz_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return QuizResultsResponse(
        quiz_id=result["quiz_id"],
        title=result["title"],
        attempts_count=result["attempts_count"],
        best_score=result["best_score"],
        topic_strengths=[TopicStrength(**t) for t in result["topic_strengths"]],
    )
