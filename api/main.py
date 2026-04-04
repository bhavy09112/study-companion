"""FastAPI application — all API endpoints for Study Companion.

Endpoints: /ingest, /generate, /quiz/start, /quiz/submit,
           /flashcards/due, /flashcards/review, /progress,
           /export/anki, /health
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.schemas import (
    IngestRequest, IngestResponse,
    GenerateRequest, GenerateResponse, Citation,
    QuizStartRequest, QuizStartResponse, Question,
    QuizSubmitRequest, QuizSubmitResponse, QuestionResult,
    FlashcardsDueResponse, Flashcard,
    FlashcardReviewRequest, FlashcardReviewResponse,
    ProgressResponse, TopicProgress,
    HealthResponse,
)

app = FastAPI(
    title="Study Companion AI",
    description="Local-first, RAG-augmented study assistant API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lazy-loaded singletons ──────────────────────────────

_engine = None
_retriever = None
_quiz_sessions: dict[str, dict] = {}


def get_engine():
    """Lazy-load inference engine."""
    global _engine
    if _engine is None:
        from inference.engine import InferenceEngine
        _engine = InferenceEngine()
    return _engine


def get_retriever():
    """Lazy-load RAG retriever."""
    global _retriever
    if _retriever is None:
        from inference.rag import HybridRetriever
        _retriever = HybridRetriever()
        try:
            _retriever.load()
        except FileNotFoundError:
            pass  # Index not built yet
    return _retriever


# ── Endpoints ───────────────────────────────────────────

@app.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    files: list[UploadFile] = File(default=[]),
    urls: Optional[str] = None,
):
    """Ingest documents: upload files and/or provide URLs.

    Runs: ingest -> clean -> chunk -> embed -> update FAISS index.
    """
    from pipeline.ingest import ingest
    from pipeline.clean import clean_documents
    from pipeline.chunk import chunk_documents
    from pipeline.embed import EmbeddingIndex, build_bm25_index

    all_docs = []
    sources = []

    # Process uploaded files
    for file in files:
        tmp_path = f"data/raw/{file.filename}"
        Path("data/raw").mkdir(parents=True, exist_ok=True)
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        try:
            docs = ingest(tmp_path)
            all_docs.extend(docs)
            sources.append(file.filename or "uploaded_file")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to ingest {file.filename}: {e}")

    # Process URLs
    if urls:
        url_list = json.loads(urls) if urls.startswith("[") else [urls]
        for url in url_list:
            try:
                docs = ingest(url)
                all_docs.extend(docs)
                sources.append(url)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to ingest URL {url}: {e}")

    if not all_docs:
        raise HTTPException(status_code=400, detail="No documents to ingest")

    # Clean and chunk
    cleaned = clean_documents(all_docs)
    chunks = chunk_documents(cleaned)

    # Save chunks
    chunks_path = Path("data/processed/chunks.jsonl")
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    with open(chunks_path, "a", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # Build/update index
    idx = EmbeddingIndex()
    idx.build(chunks)
    idx.save()
    build_bm25_index(chunks)

    # Reload retriever
    global _retriever
    _retriever = None

    return IngestResponse(
        chunks_added=len(chunks),
        sources=sources,
        index_size=idx.size,
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate_study_material(req: GenerateRequest):
    """Generate study material for a topic using RAG + LLM."""
    from inference.formatter import format_output, detect_domain, add_confidence_indicator

    engine = get_engine()
    retriever = get_retriever()

    # Retrieve context
    rag_result = retriever.search_with_uncertainty(req.topic, top_k=req.top_k)
    context_chunks = rag_result["results"]

    # Build mode-specific system prompt
    mode_prompts = {
        "simple_explanation": "Explain the topic in simple terms a 15-year-old would understand. Use analogies.",
        "key_concepts": "Extract and define the key concepts. Number each concept.",
        "exam_critical": "List the must-remember, exam-critical facts and formulas.",
        "detailed_explanation": "Provide a detailed explanation with worked examples and step-by-step reasoning.",
        "common_mistakes": "List common mistakes and misconceptions. Explain why each is wrong.",
        "practice_questions": "Generate 3 MCQs (with answers), 2 short-answer questions, and 1 problem-solving question.",
        "revision_sheet": "Create a concise one-page revision sheet with key formulas, definitions, and quick lists.",
        "mnemonics": "Create creative memory tricks, mnemonics, and analogies for the key information.",
        "concept_map": "Create a concept map using Mermaid diagram syntax showing relationships between key concepts.",
    }

    system_prompt = (
        "You are a study assistant. " +
        mode_prompts.get(req.mode, "Help the student study this topic.") +
        " Base your answer on the provided context material."
    )

    # Generate
    result = engine.generate(
        prompt=f"Topic: {req.topic}",
        system_prompt=system_prompt,
        context_chunks=context_chunks,
        temperature=req.temperature,
    )

    # Detect domain and format
    domain = req.domain or detect_domain(
        " ".join(c.get("text", "") for c in context_chunks)
    )
    formatted = format_output(result["text"], req.mode, domain, context_chunks)

    # Add confidence indicator
    formatted = add_confidence_indicator(formatted, rag_result["max_score"])

    # Build citations
    citations = [
        Citation(
            chunk_id=c.get("chunk_id", ""),
            source=c.get("source", "unknown"),
            page=c.get("page", 1),
            score=c.get("score", 0.0),
        )
        for c in context_chunks
        if c.get("relevant", True)
    ]

    return GenerateResponse(
        output=formatted,
        mode=req.mode,
        domain=domain,
        sources=citations,
        uncertain=rag_result["uncertain"],
        warnings=result.get("warnings", []),
    )


@app.post("/quiz/start", response_model=QuizStartResponse)
async def start_quiz(req: QuizStartRequest):
    """Start a quiz session with generated questions."""
    engine = get_engine()
    retriever = get_retriever()

    questions = []
    for topic in req.topics:
        # Retrieve context for the topic
        results = retriever.search(topic, top_k=3)
        context = " ".join(r.get("text", "") for r in results)

        # Generate questions
        prompt = (
            f"Generate {req.n_questions // len(req.topics)} multiple choice questions about: {topic}\n"
            f"Context: {context[:1000]}\n\n"
            "Format each question as:\nQ: [question]\nA) [option]\nB) [option]\nC) [option]\nD) [option]\nAnswer: [letter]\n"
        )

        result = engine.generate(prompt=prompt, temperature=0.8)

        # Parse questions from output
        q_blocks = result["text"].split("\nQ:")
        for i, block in enumerate(q_blocks):
            if not block.strip():
                continue
            q_id = str(uuid.uuid4())
            # Extract options
            options = []
            for letter in "ABCD":
                import re
                match = re.search(rf"{letter}\)\s*(.+?)(?:\n|$)", block)
                if match:
                    options.append(match.group(1).strip())

            q_text = block.split("\n")[0].strip().lstrip(": ")
            if q_text:
                questions.append(Question(
                    id=q_id,
                    text=q_text,
                    question_type="mcq",
                    options=options if options else None,
                    topic=topic,
                ))

    session_id = str(uuid.uuid4())
    _quiz_sessions[session_id] = {
        "questions": questions,
        "start_time": None,
        "time_limit": req.time_limit_seconds,
    }

    return QuizStartResponse(
        session_id=session_id,
        questions=questions[:req.n_questions],
        time_limit_seconds=req.time_limit_seconds,
    )


@app.post("/quiz/submit", response_model=QuizSubmitResponse)
async def submit_quiz(req: QuizSubmitRequest):
    """Submit quiz answers and get results."""
    session = _quiz_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")

    # Simple scoring (without exact answer matching since LLM-generated)
    results = []
    correct_count = 0
    topic_scores: dict[str, list[bool]] = {}

    for answer in req.answers:
        # For now, mark as correct if answer is provided (actual grading needs model)
        is_correct = len(answer.answer.strip()) > 0
        correct_count += is_correct

        results.append(QuestionResult(
            question_id=answer.question_id,
            correct=is_correct,
            correct_answer="See explanation",
            explanation="Review the study material for this topic.",
        ))

        # Track per-topic
        for q in session["questions"]:
            if q.id == answer.question_id:
                if q.topic not in topic_scores:
                    topic_scores[q.topic] = []
                topic_scores[q.topic].append(is_correct)

    score = correct_count / max(len(req.answers), 1)
    weak_topics = [
        topic for topic, scores in topic_scores.items()
        if sum(scores) / len(scores) < 0.6
    ]

    return QuizSubmitResponse(
        score=score,
        breakdown=results,
        weak_topics=weak_topics,
    )


@app.get("/flashcards/due", response_model=FlashcardsDueResponse)
async def get_due_flashcards():
    """Get flashcards due for review."""
    from srs.db import get_due_cards

    cards = get_due_cards(limit=20)
    flashcards = [
        Flashcard(
            id=c["id"],
            front=c["front"],
            back=c["back"],
            topic=c.get("topic"),
            ease_factor=c.get("ease_factor"),
            interval_days=c.get("interval_days"),
            next_review_at=c.get("next_review_at"),
        )
        for c in cards
    ]

    return FlashcardsDueResponse(cards=flashcards, count=len(flashcards))


@app.post("/flashcards/review", response_model=FlashcardReviewResponse)
async def review_flashcard(req: FlashcardReviewRequest):
    """Review a flashcard with SM-2 quality rating."""
    from srs.scheduler import review_card

    schedule = review_card(req.card_id, req.quality)

    return FlashcardReviewResponse(
        interval_days=schedule["interval_days"],
        ease_factor=schedule["ease_factor"],
        next_review_at=schedule["next_review_at"],
    )


@app.get("/progress", response_model=ProgressResponse)
async def get_progress():
    """Get study progress across all topics."""
    from srs.db import get_topic_progress, get_card_count

    topics_data = get_topic_progress()
    total_cards = get_card_count()

    topics = [
        TopicProgress(
            name=t["name"],
            mastery_score=t.get("mastery_score", 0.0),
            card_count=t.get("card_count", 0),
            last_studied_at=t.get("last_studied_at"),
        )
        for t in topics_data
    ]

    overall = sum(t.mastery_score for t in topics) / max(len(topics), 1)

    return ProgressResponse(
        topics=topics,
        overall_mastery=round(overall, 3),
        total_cards=total_cards,
    )


@app.get("/export/anki")
async def export_anki():
    """Export all flashcards as an Anki .apkg file."""
    from srs.flashcard_export import export_to_anki

    try:
        path = export_to_anki("Study Companion")
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename="study_companion.apkg",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    from srs.db import get_card_count

    engine = get_engine()
    retriever = get_retriever()
    health = engine.health_check()

    return HealthResponse(
        model_loaded=health["model_loaded"],
        model_name=health.get("model_name", ""),
        vram_used_gb=health.get("vram_used_gb", 0.0),
        index_size=retriever.index_size,
        db_cards=get_card_count(),
        status="ok" if health["model_loaded"] else "degraded",
    )
