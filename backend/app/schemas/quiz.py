import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Quiz Generation ──


class QuizGenerateRequest(BaseModel):
    document_id: uuid.UUID | None = Field(
        None, description="Generate from a specific document"
    )
    topic: str | None = Field(
        None, max_length=500, description="Topic to generate questions about"
    )
    question_count: int = Field(default=5, ge=1, le=20)
    question_types: list[str] = Field(
        default=["mcq"],
        description="Types of questions: 'mcq', 'short_answer', or both",
    )


class MCQOption(BaseModel):
    label: str  # A, B, C, D
    text: str
    is_correct: bool = False


class QuizQuestionResponse(BaseModel):
    id: uuid.UUID
    question_type: str
    question_text: str
    options: list[MCQOption] | None = None
    source_pages: str | None

    model_config = {"from_attributes": True}


class QuizQuestionWithAnswer(QuizQuestionResponse):
    correct_answer: str
    explanation: str | None


class QuizResponse(BaseModel):
    id: uuid.UUID
    title: str
    topic: str | None
    document_id: uuid.UUID | None
    question_count: int
    questions: list[QuizQuestionResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class QuizListResponse(BaseModel):
    quizzes: list[QuizResponse]
    total: int


# ── Quiz Attempt ──


class AnswerSubmission(BaseModel):
    question_id: uuid.UUID
    answer: str


class QuizAttemptRequest(BaseModel):
    answers: list[AnswerSubmission]


class QuestionFeedback(BaseModel):
    question_id: uuid.UUID
    question_text: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str | None
    feedback: str | None
    source_pages: str | None


class QuizAttemptResponse(BaseModel):
    quiz_id: uuid.UUID
    total_questions: int
    correct_count: int
    score_percentage: float
    feedback: list[QuestionFeedback]


# ── Progress Tracking ──


class TopicStrength(BaseModel):
    topic: str
    total_questions: int
    correct_count: int
    accuracy: float
    needs_reinforcement: bool


class QuizResultsResponse(BaseModel):
    quiz_id: uuid.UUID
    title: str
    attempts_count: int
    best_score: float
    topic_strengths: list[TopicStrength]
