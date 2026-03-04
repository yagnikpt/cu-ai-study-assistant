"""Quiz generation and grading service.

Generates MCQ and short-answer questions from course material,
maps questions to source chunks, and provides feedback on attempts.
"""

import json
import logging
import uuid

from google import genai

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Document,
    DocumentChunk,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    QuestionType,
)
from app.services.embeddings import embed_query
from app.services.genai_client import get_genai_client
from app.services.vector_search import search_similar_chunks

logger = logging.getLogger(__name__)

QUIZ_SYSTEM_PROMPT = """You are an AI study assistant that generates quiz questions from educational material.

You MUST respond with valid JSON only - no markdown, no code fences, no extra text.

Rules:
1. Generate questions ONLY from the provided source material.
2. Each question must be clearly answerable from the source text.
3. For MCQ: provide 4 options (A, B, C, D) with exactly one correct answer.
4. For short_answer: the correct answer should be concise (1-3 sentences).
5. Include an explanation for why the answer is correct, citing the source.
6. Include the source page numbers for each question.
7. Questions should test understanding, not just memorization.
8. Vary difficulty levels within the quiz.

Output ONLY valid JSON matching this exact schema:
{
  "questions": [
    {
      "question_type": "mcq",
      "question_text": "What is...?",
      "options": [
        {"label": "A", "text": "Option text", "is_correct": false},
        {"label": "B", "text": "Option text", "is_correct": true},
        {"label": "C", "text": "Option text", "is_correct": false},
        {"label": "D", "text": "Option text", "is_correct": false}
      ],
      "correct_answer": "B",
      "explanation": "The answer is B because... [Source: doc, p.X]",
      "source_pages": "p.5"
    },
    {
      "question_type": "short_answer",
      "question_text": "Explain...",
      "options": null,
      "correct_answer": "The concept is...",
      "explanation": "This is correct because... [Source: doc, p.X]",
      "source_pages": "pp.3-4"
    }
  ]
}
"""


async def generate_quiz(
    db: AsyncSession,
    document_id: uuid.UUID | None = None,
    topic: str | None = None,
    question_count: int = 5,
    question_types: list[str] | None = None,
    space_id: uuid.UUID | None = None,
) -> Quiz:
    """Generate a quiz from course materials.

    Args:
        db: Async database session.
        document_id: Generate from a specific document.
        topic: Topic to generate questions about.
        question_count: Number of questions to generate.
        question_types: List of question types ('mcq', 'short_answer').

    Returns:
        Quiz ORM object with questions populated.
    """
    if question_types is None:
        question_types = ["mcq"]

    # Retrieve relevant chunks
    chunks: list[dict] = []
    effective_topic = topic or "General"

    if topic:
        query_embedding = await embed_query(topic)
        # Scope to space docs if space_id provided
        doc_ids = None
        if document_id:
            doc_ids = [document_id]
        elif space_id:
            result = await db.execute(
                select(Document.id).where(
                    Document.space_id == space_id, Document.status == "ready"
                )
            )
            doc_ids = list(result.scalars().all())
        chunks = await search_similar_chunks(
            db=db,
            query_embedding=query_embedding,
            top_k=10,
            document_ids=doc_ids,
        )
    elif document_id:
        # Get chunks from the document directly
        query = (
            select(DocumentChunk, Document.original_filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(DocumentChunk.chunk_index)
            .limit(15)
        )
        result = await db.execute(query)
        rows = result.all()

        for chunk, doc_name in rows:
            chunks.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_name": doc_name,
                    "content": chunk.content,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "section_title": chunk.section_title,
                    "score": 1.0,
                }
            )

        # Derive topic from document
        doc = await db.get(Document, document_id)
        if doc:
            effective_topic = doc.original_filename.rsplit(".", 1)[0]

    if not chunks:
        raise ValueError("No source material found to generate quiz from.")

    # Build context
    context_parts = []
    chunk_id_map: dict[int, uuid.UUID] = {}  # source_index -> chunk_id
    for i, chunk in enumerate(chunks, 1):
        pages = (
            f"p.{chunk['page_start']}"
            if chunk["page_start"] == chunk["page_end"]
            else f"pp.{chunk['page_start']}-{chunk['page_end']}"
        )
        section = (
            f" | Section: {chunk['section_title']}"
            if chunk.get("section_title")
            else ""
        )
        header = f"[Source {i}: {chunk['document_name']}, {pages}{section}]"
        context_parts.append(f"{header}\n{chunk['content']}")
        chunk_id_map[i] = chunk["chunk_id"]

    context = "\n\n---\n\n".join(context_parts)

    types_str = " and ".join(question_types)
    user_prompt = f"""Generate exactly {question_count} quiz questions ({types_str}) from this material about: {effective_topic}

SOURCE MATERIAL:
{context}

Generate the questions as JSON."""

    # Generate with Gemini
    client = get_genai_client()
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=QUIZ_SYSTEM_PROMPT,
            temperature=0.5,
            max_output_tokens=4096,
        ),
    )

    raw_text = response.text or ""

    # Clean up potential markdown code fences
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        # Remove first line (```json or ```) and last line (```)
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1])

    try:
        quiz_data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse quiz JSON: {e}\nRaw: {raw_text[:500]}")
        raise ValueError(
            "Failed to generate valid quiz questions. Please try again."
        ) from e

    # Create Quiz record
    quiz = Quiz(
        title=f"Quiz: {effective_topic}",
        document_id=document_id,
        space_id=space_id,
        topic=effective_topic,
        question_count=len(quiz_data.get("questions", [])),
    )
    db.add(quiz)
    await db.flush()  # Get the quiz ID

    # Create QuizQuestion records
    for q_data in quiz_data.get("questions", []):
        q_type = (
            QuestionType.MCQ
            if q_data.get("question_type") == "mcq"
            else QuestionType.SHORT_ANSWER
        )

        question = QuizQuestion(
            quiz_id=quiz.id,
            question_type=q_type,
            question_text=q_data["question_text"],
            options=q_data.get("options"),
            correct_answer=q_data["correct_answer"],
            explanation=q_data.get("explanation"),
            source_chunk_ids=[str(cid) for cid in chunk_id_map.values()],
            source_pages=q_data.get("source_pages"),
        )
        db.add(question)

    await db.flush()

    logger.info(f"Generated quiz '{quiz.title}' with {quiz.question_count} questions")
    return quiz


async def grade_attempt(
    db: AsyncSession,
    quiz_id: uuid.UUID,
    answers: list[dict],
) -> dict:
    """Grade a quiz attempt and provide feedback.

    Args:
        db: Async database session.
        quiz_id: The quiz being attempted.
        answers: List of {question_id, answer} dicts.

    Returns:
        Grading results with per-question feedback.
    """
    # Fetch quiz with questions
    quiz = await db.get(Quiz, quiz_id)
    if not quiz:
        raise ValueError(f"Quiz {quiz_id} not found")

    questions_result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
    )
    questions = {q.id: q for q in questions_result.scalars().all()}

    feedback_list = []
    correct_count = 0

    for ans in answers:
        q_id = ans["question_id"]
        if isinstance(q_id, str):
            q_id = uuid.UUID(q_id)

        question = questions.get(q_id)
        if not question:
            continue

        user_answer = ans["answer"].strip()
        is_correct = False

        if question.question_type == QuestionType.MCQ:
            # For MCQ, compare the selected option label
            is_correct = user_answer.upper() == question.correct_answer.upper()
        else:
            # For short answer, do a basic semantic comparison
            # (In production, you'd use LLM-based grading here)
            is_correct = (
                user_answer.lower().strip() in question.correct_answer.lower().strip()
            )

        if is_correct:
            correct_count += 1

        # Generate feedback for incorrect answers
        feedback_text = None
        if not is_correct:
            feedback_text = f"The correct answer is: {question.correct_answer}"
            if question.explanation:
                feedback_text += f"\n\nExplanation: {question.explanation}"

        # Record attempt
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            question_id=q_id,
            user_answer=user_answer,
            is_correct=is_correct,
            feedback=feedback_text,
        )
        db.add(attempt)

        feedback_list.append(
            {
                "question_id": q_id,
                "question_text": question.question_text,
                "user_answer": user_answer,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "explanation": question.explanation,
                "feedback": feedback_text,
                "source_pages": question.source_pages,
            }
        )

    total = len(feedback_list)
    score = (correct_count / total * 100) if total > 0 else 0

    logger.info(
        f"Graded quiz {quiz_id}: {correct_count}/{total} correct ({score:.1f}%)"
    )

    return {
        "quiz_id": quiz_id,
        "total_questions": total,
        "correct_count": correct_count,
        "score_percentage": round(score, 1),
        "feedback": feedback_list,
    }


async def get_quiz_results(
    db: AsyncSession,
    quiz_id: uuid.UUID,
) -> dict:
    """Get aggregated results and topic analysis for a quiz.

    Args:
        db: Async database session.
        quiz_id: The quiz to get results for.

    Returns:
        Results dict with attempts count, best score, and topic strengths.
    """
    quiz = await db.get(Quiz, quiz_id)
    if not quiz:
        raise ValueError(f"Quiz {quiz_id} not found")

    # Get all attempts for this quiz
    attempts_result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.quiz_id == quiz_id)
        .order_by(QuizAttempt.attempted_at)
    )
    attempts = attempts_result.scalars().all()

    if not attempts:
        return {
            "quiz_id": quiz_id,
            "title": quiz.title,
            "attempts_count": 0,
            "best_score": 0.0,
            "topic_strengths": [],
        }

    # Group attempts by question to track per-question accuracy
    question_stats: dict[uuid.UUID, dict] = {}
    for attempt in attempts:
        if attempt.question_id not in question_stats:
            question_stats[attempt.question_id] = {
                "total": 0,
                "correct": 0,
            }
        question_stats[attempt.question_id]["total"] += 1
        if attempt.is_correct:
            question_stats[attempt.question_id]["correct"] += 1

    # Calculate overall stats
    total_questions = len(question_stats)
    total_correct = sum(s["correct"] for s in question_stats.values())
    total_attempts_count = sum(s["total"] for s in question_stats.values())
    best_score = (total_correct / total_questions * 100) if total_questions > 0 else 0

    # Topic strengths (use quiz topic as single topic for MVP)
    topic_strengths = []
    if quiz.topic:
        accuracy = (
            (total_correct / total_attempts_count * 100)
            if total_attempts_count > 0
            else 0
        )
        topic_strengths.append(
            {
                "topic": quiz.topic,
                "total_questions": total_questions,
                "correct_count": total_correct,
                "accuracy": round(accuracy, 1),
                "needs_reinforcement": accuracy < 70,
            }
        )

    return {
        "quiz_id": quiz_id,
        "title": quiz.title,
        "attempts_count": total_attempts_count,
        "best_score": round(best_score, 1),
        "topic_strengths": topic_strengths,
    }
