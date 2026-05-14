"""Pydantic models for API request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Ingest ──────────────────────────────────────────────

class IngestRequest(BaseModel):
    """Request body for document ingestion."""
    urls: list[str] = Field(default_factory=list, description="List of URLs to ingest")


class IngestResponse(BaseModel):
    """Response from document ingestion."""
    chunks_added: int
    sources: list[str]
    index_size: int


# ── Generate ────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """Request body for study material generation."""
    topic: str = Field(..., description="Topic or question to study")
    mode: str = Field(
        default="simple_explanation",
        description="Output mode: simple_explanation, key_concepts, exam_critical, "
                    "detailed_explanation, common_mistakes, practice_questions, "
                    "revision_sheet, mnemonics, concept_map",
    )
    domain: Optional[str] = Field(default=None, description="Force domain (auto-detect if null)")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class Citation(BaseModel):
    """Source citation for a generated response."""
    chunk_id: str
    source: str
    page: int = 1
    score: float = 0.0


class GenerateResponse(BaseModel):
    """Response from study material generation."""
    output: str
    mode: str
    domain: str
    sources: list[Citation]
    uncertain: bool = False
    warnings: list[str] = Field(default_factory=list)


# ── Quiz ────────────────────────────────────────────────

class QuizStartRequest(BaseModel):
    """Request to start a quiz session."""
    topics: list[str]
    n_questions: int = Field(default=5, ge=1, le=50)
    time_limit_seconds: int = Field(default=300, ge=30)


class Question(BaseModel):
    """A quiz question."""
    id: str
    text: str
    question_type: str = "mcq"  # mcq, short_answer, problem
    options: Optional[list[str]] = None
    topic: str = ""


class QuizStartResponse(BaseModel):
    """Response with quiz questions."""
    session_id: str
    questions: list[Question]
    time_limit_seconds: int


class Answer(BaseModel):
    """A submitted answer."""
    question_id: str
    answer: str


class QuizSubmitRequest(BaseModel):
    """Request to submit quiz answers."""
    session_id: str
    answers: list[Answer]


class QuestionResult(BaseModel):
    """Result for a single question."""
    question_id: str
    correct: bool
    correct_answer: str
    explanation: str = ""


class QuizSubmitResponse(BaseModel):
    """Response from quiz submission."""
    score: float
    breakdown: list[QuestionResult]
    weak_topics: list[str]


# ── Flashcards ──────────────────────────────────────────

class Flashcard(BaseModel):
    """A flashcard for SRS review."""
    id: str
    front: str
    back: str
    topic: Optional[str] = None
    ease_factor: Optional[float] = None
    interval_days: Optional[float] = None
    next_review_at: Optional[str] = None


class FlashcardsDueResponse(BaseModel):
    """Response with due flashcards."""
    cards: list[Flashcard]
    count: int


class FlashcardReviewRequest(BaseModel):
    """Request to review a flashcard."""
    card_id: str
    quality: int = Field(..., ge=0, le=5, description="SM-2 quality rating 0-5")


class FlashcardReviewResponse(BaseModel):
    """Response from flashcard review."""
    interval_days: float
    ease_factor: float
    next_review_at: str


# ── Progress ────────────────────────────────────────────

class TopicProgress(BaseModel):
    """Progress for a single topic."""
    name: str
    mastery_score: float
    card_count: int = 0
    last_studied_at: Optional[str] = None


class ProgressResponse(BaseModel):
    """Overall study progress."""
    topics: list[TopicProgress]
    overall_mastery: float
    total_cards: int


# ── Health ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response."""
    model_loaded: bool
    model_name: str = ""
    vram_used_gb: float = 0.0
    index_size: int = 0
    db_cards: int = 0
    status: str = "ok"


# ── Refine (Quick Actions) ──────────────────────────────

class RefineRequest(BaseModel):
    """Apply a quick action to existing content."""
    content: str
    action: str = Field(..., description="summarize | simplify | translate | elaborate")
    target_language: Optional[str] = Field(default=None, description="For translate")


class RefineResponse(BaseModel):
    output: str
    action: str


# ── Make Flashcards ─────────────────────────────────────

class FlashcardsFromTextRequest(BaseModel):
    text: str = Field(..., description="Source text to extract Q/A pairs from")
    topic: Optional[str] = None
    n_cards: int = Field(default=8, ge=1, le=30)


class FlashcardsFromTextResponse(BaseModel):
    cards_added: int
    cards: list[Flashcard]


# ── Quiz Extras ─────────────────────────────────────────

class QuizHintRequest(BaseModel):
    question_id: str
    session_id: str


class QuizHintResponse(BaseModel):
    hint: str


class QuizFlagRequest(BaseModel):
    session_id: str
    question_id: str
    flagged: bool = True


class QuizFlagResponse(BaseModel):
    flagged_ids: list[str]


# ── Index Management ────────────────────────────────────

class IndexedFile(BaseModel):
    source: str
    chunk_count: int


class IndexFilesResponse(BaseModel):
    files: list[IndexedFile]
    total_chunks: int


class ClearIndexResponse(BaseModel):
    cleared: bool
    deleted_chunks: int


# ── Sessions / Activity ─────────────────────────────────

class RecentSession(BaseModel):
    id: str
    topic: Optional[str] = None
    kind: str
    duration_seconds: int = 0
    score: Optional[float] = None
    impact_score: Optional[float] = None
    started_at: str


class RecentSessionsResponse(BaseModel):
    sessions: list[RecentSession]


class HeatmapDay(BaseModel):
    day: str
    count: int
    duration: int


class HeatmapResponse(BaseModel):
    days: list[HeatmapDay]


class LogSessionRequest(BaseModel):
    kind: str = Field(..., description="study | quiz | flashcards")
    topic: Optional[str] = None
    duration_seconds: int = 0
    score: Optional[float] = None
    impact_score: Optional[float] = None


class LogSessionResponse(BaseModel):
    id: str


# ── Search ──────────────────────────────────────────────

class SearchHit(BaseModel):
    kind: str  # chunk | card | bookmark
    title: str
    snippet: str
    score: float = 0.0
    extra: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


# ── Bookmarks ───────────────────────────────────────────

class Bookmark(BaseModel):
    id: str
    topic: Optional[str] = None
    mode: Optional[str] = None
    content: str
    created_at: str


class BookmarkCreateRequest(BaseModel):
    content: str
    topic: Optional[str] = None
    mode: Optional[str] = None


class BookmarksResponse(BaseModel):
    bookmarks: list[Bookmark]


# ── Flashcard Undo ──────────────────────────────────────

class UndoReviewRequest(BaseModel):
    card_id: str


class UndoReviewResponse(BaseModel):
    undone: bool


# ── Dashboard Metrics ───────────────────────────────────

class DashboardMetrics(BaseModel):
    study_hours_total: float
    study_hours_week: float
    weekly_goal_percent: float
    flashcard_retention: float
    review_due_count: int
    mastered_count: int
    quiz_avg_score: Optional[float] = None
    quiz_letter_grade: str = ""
