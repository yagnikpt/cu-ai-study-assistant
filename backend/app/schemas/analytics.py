"""Analytics response schemas."""

from pydantic import BaseModel


class DocumentStats(BaseModel):
    total: int = 0
    ready: int = 0
    processing: int = 0
    failed: int = 0


class QuizScorePoint(BaseModel):
    """A single data point for the quiz score trend."""

    date: str  # ISO date
    score: float  # percentage 0-100


class TopicStrengthItem(BaseModel):
    topic: str
    accuracy: float  # 0-100
    total_questions: int


class StudyPlanStats(BaseModel):
    total_plans: int = 0
    topics_total: int = 0
    topics_completed: int = 0
    estimated_hours: float = 0.0


class ActivityDay(BaseModel):
    """Activity counts for a single day."""

    date: str  # ISO date
    documents: int = 0
    quizzes: int = 0
    plans: int = 0


class ProfileAnalytics(BaseModel):
    spaces_count: int = 0
    document_stats: DocumentStats = DocumentStats()
    quiz_count: int = 0
    quiz_attempts_count: int = 0
    quiz_avg_score: float = 0.0
    quiz_score_trend: list[QuizScorePoint] = []
    topic_strengths: list[TopicStrengthItem] = []
    study_plan_stats: StudyPlanStats = StudyPlanStats()
    activity: list[ActivityDay] = []
