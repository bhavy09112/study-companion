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
