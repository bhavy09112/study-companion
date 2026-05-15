"""FastAPI application — all API endpoints for Study Companion.

Endpoints:
  /ingest, /generate, /generate/refine,
  /quiz/start, /quiz/submit, /quiz/hint, /quiz/flag,
  /flashcards/due, /flashcards/review, /flashcards/from-text, /flashcards/undo,
  /progress, /dashboard, /sessions/recent, /sessions, /activity/heatmap,
  /export/anki, /index/files, /index (DELETE), /bookmarks, /search, /health
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Prefer locally-cached HF models; never block on network at request time.
# Set STUDY_COMPANION_ALLOW_HF_DOWNLOAD=1 to allow downloads (first-time setup).
if os.getenv("STUDY_COMPANION_ALLOW_HF_DOWNLOAD") != "1":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.schemas import (
    IngestRequest, IngestResponse,
    GenerateRequest, GenerateResponse, Citation,
    QuizStartRequest, QuizStartResponse, Question,
    QuizSubmitRequest, QuizSubmitResponse, QuestionResult,
    FlashcardsDueResponse, Flashcard,
    FlashcardReviewRequest, FlashcardReviewResponse,
    ProgressResponse, TopicProgress,
    HealthResponse,
    RefineRequest, RefineResponse,
    FlashcardsFromTextRequest, FlashcardsFromTextResponse,
    QuizHintRequest, QuizHintResponse,
    QuizFlagRequest, QuizFlagResponse,
    IndexedFile, IndexFilesResponse, ClearIndexResponse,
    RecentSession, RecentSessionsResponse,
    HeatmapDay, HeatmapResponse,
    LogSessionRequest, LogSessionResponse,
    SearchHit, SearchResponse,
    Bookmark, BookmarkCreateRequest, BookmarksResponse,
    UndoReviewRequest, UndoReviewResponse,
    DashboardMetrics,
)

app = FastAPI(
    title="Study Companion AI",
    description="Local-first, RAG-augmented study assistant API",
    version="1.2.0",
)

# CORS — UI is served same-origin by FastAPI, so CORS is only needed if
# someone runs an external client. Set STUDY_COMPANION_CORS_ORIGINS to override.
_default_origins = "http://localhost:8000,http://127.0.0.1:8000"
_origins = [
    o.strip()
    for o in os.getenv("STUDY_COMPANION_CORS_ORIGINS", _default_origins).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Static frontend ─────────────────────────────────────

WEB_DIR = (Path(__file__).resolve().parent.parent / "web")
if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


def _serve_html(name: str) -> HTMLResponse:
    path = WEB_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
async def home():
    return _serve_html("index.html")


@app.get("/quiz", response_class=HTMLResponse)
async def page_quiz():
    return _serve_html("quiz.html")


@app.get("/flashcards", response_class=HTMLResponse)
async def page_flashcards():
    return _serve_html("flashcards.html")


@app.get("/progress-page", response_class=HTMLResponse)
async def page_progress():
    return _serve_html("progress.html")


@app.get("/settings", response_class=HTMLResponse)
async def page_settings():
    return _serve_html("settings.html")

# ── Constants ───────────────────────────────────────────

ALLOWED_UPLOAD_EXTS = {
    ".pdf", ".docx", ".txt", ".md", ".rst",
    ".png", ".jpg", ".jpeg", ".webp", ".html", ".htm",
}
DATA_RAW = Path("data/raw").resolve()
EMBEDDINGS_DIR = Path("data/embeddings").resolve()
PROCESSED_DIR = Path("data/processed").resolve()


def _safe_upload_path(filename: Optional[str]) -> Path:
    """Sanitize an attacker-controlled filename to a safe path under data/raw."""
    name = Path(filename or "upload.bin").name  # strip dir components
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")
    suffix = Path(name).suffix.lower()
    if suffix and suffix not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    target = (DATA_RAW / name).resolve()
    try:
        target.relative_to(DATA_RAW)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return target


# ── Lazy-loaded singletons ──────────────────────────────

_engine = None
_retriever = None
_quiz_sessions: dict[str, dict] = {}


def get_engine():
    global _engine
    if _engine is None:
        from inference.engine import InferenceEngine
        _engine = InferenceEngine()
    return _engine


def get_retriever():
    global _retriever
    if _retriever is None:
        from inference.rag import HybridRetriever
        _retriever = HybridRetriever()
        try:
            _retriever.load()
        except FileNotFoundError:
            pass
        except Exception as e:  # offline / model not cached — degrade, don't crash
            print(f"Retriever load failed (degraded mode): {e}", file=sys.stderr)
    return _retriever


# ── Ingest ──────────────────────────────────────────────

@app.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    files: list[UploadFile] = File(default=[]),
    urls: Optional[str] = None,
):
    """Ingest documents: upload files and/or provide URLs."""
    from pipeline.ingest import ingest
    from pipeline.clean import clean_documents
    from pipeline.chunk import chunk_documents
    from pipeline.embed import EmbeddingIndex, build_bm25_index

    all_docs = []
    sources: list[str] = []

    for file in files:
        target = _safe_upload_path(file.filename)
        content = await file.read()
        target.write_bytes(content)
        try:
            docs = ingest(str(target))
            all_docs.extend(docs)
            sources.append(target.name)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to ingest {target.name}: {e}")

    if urls:
        try:
            url_list = json.loads(urls) if urls.lstrip().startswith("[") else [urls]
        except json.JSONDecodeError:
            url_list = [urls]
        for url in url_list:
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise HTTPException(status_code=400, detail=f"Invalid URL: {url}")
            try:
                docs = ingest(url)
                all_docs.extend(docs)
                sources.append(url)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to ingest URL {url}: {e}")

    if not all_docs:
        raise HTTPException(status_code=400, detail="No documents to ingest")

    cleaned = clean_documents(all_docs)
    chunks = chunk_documents(cleaned)

    chunks_path = Path("data/processed/chunks.jsonl")
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    with open(chunks_path, "a", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    idx = EmbeddingIndex()
    idx.build(chunks)
    idx.save()
    build_bm25_index(chunks)

    global _retriever
    _retriever = None

    return IngestResponse(
        chunks_added=len(chunks),
        sources=sources,
        index_size=idx.size,
    )


# ── Generate ────────────────────────────────────────────

MODE_PROMPTS: dict[str, str] = {
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


@app.post("/generate", response_model=GenerateResponse)
async def generate_study_material(req: GenerateRequest):
    """Generate study material for a topic using RAG + LLM."""
    from inference.formatter import format_output, detect_domain, add_confidence_indicator

    engine = get_engine()
    retriever = get_retriever()

    rag_result = retriever.search_with_uncertainty(req.topic, top_k=req.top_k)
    context_chunks = rag_result["results"]

    system_prompt = (
        "You are a study assistant. "
        + MODE_PROMPTS.get(req.mode, "Help the student study this topic.")
        + " Base your answer on the provided context material."
    )

    result = engine.generate(
        prompt=f"Topic: {req.topic}",
        system_prompt=system_prompt,
        context_chunks=context_chunks,
        temperature=req.temperature,
    )

    domain = req.domain or detect_domain(
        " ".join(c.get("text", "") for c in context_chunks)
    )
    formatted = format_output(result["text"], req.mode, domain, context_chunks)
    formatted = add_confidence_indicator(formatted, rag_result["max_score"])

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


@app.post("/generate/refine", response_model=RefineResponse)
async def refine_content(req: RefineRequest):
    """Apply a quick action (summarize/simplify/translate/elaborate) to text."""
    engine = get_engine()

    action_prompts = {
        "summarize": "Summarize the following study content in 5 concise bullet points, preserving the key facts.",
        "simplify": "Rewrite the following study content in simpler language a 12-year-old could follow, keeping all facts intact.",
        "elaborate": "Expand the following study content with worked examples, deeper explanations, and additional context.",
    }
    if req.action == "translate":
        lang = (req.target_language or "Spanish").strip()
        system = f"Translate the following content into {lang}. Preserve markdown formatting and technical terms."
    elif req.action in action_prompts:
        system = action_prompts[req.action]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    result = engine.generate(
        prompt=req.content,
        system_prompt=system,
        temperature=0.4,
    )
    return RefineResponse(output=result["text"], action=req.action)


# ── Flashcards from Text ────────────────────────────────

@app.post("/flashcards/from-text", response_model=FlashcardsFromTextResponse)
async def flashcards_from_text(req: FlashcardsFromTextRequest):
    """Use the LLM to extract Q/A pairs from text and add them as cards."""
    from srs.db import add_card

    engine = get_engine()
    system = (
        f"Extract exactly {req.n_cards} flashcards from the content below. "
        "Output each card on its own line in the EXACT format:\n"
        "Q: <question>\nA: <answer>\n\n"
        "Keep questions concise and answers under 2 sentences. Do not number the cards."
    )
    result = engine.generate(prompt=req.text, system_prompt=system, temperature=0.3)

    text = result["text"]
    pairs: list[tuple[str, str]] = []
    blocks = re.split(r"\n\s*\n", text)
    for blk in blocks:
        q_match = re.search(r"Q:\s*(.+)", blk)
        a_match = re.search(r"A:\s*(.+)", blk, re.DOTALL)
        if q_match and a_match:
            q = q_match.group(1).strip()
            a = a_match.group(1).strip().split("\nQ:")[0].strip()
            if q and a:
                pairs.append((q, a))

    added: list[Flashcard] = []
    for q, a in pairs[: req.n_cards]:
        cid = add_card(front=q, back=a, topic=req.topic)
        added.append(Flashcard(id=cid, front=q, back=a, topic=req.topic))

    return FlashcardsFromTextResponse(cards_added=len(added), cards=added)


# ── Quiz ────────────────────────────────────────────────

@app.post("/quiz/start", response_model=QuizStartResponse)
async def start_quiz(req: QuizStartRequest):
    """Start a quiz session with generated questions."""
    engine = get_engine()
    retriever = get_retriever()

    questions: list[Question] = []
    answer_keys: dict[str, str] = {}

    n_per_topic = max(1, req.n_questions // max(len(req.topics), 1))
    for topic in req.topics:
        results = retriever.search(topic, top_k=3)
        context = " ".join(r.get("text", "") for r in results)

        prompt = (
            f"Generate {n_per_topic} multiple choice questions about: {topic}\n"
            f"Context: {context[:1500]}\n\n"
            "Format each question EXACTLY as:\n"
            "Q: [question]\nA) [option]\nB) [option]\nC) [option]\nD) [option]\nAnswer: [letter]\n\n"
        )
        result = engine.generate(prompt=prompt, temperature=0.8)

        q_blocks = re.split(r"\nQ:|^Q:", result["text"])
        for block in q_blocks:
            if not block.strip():
                continue
            q_id = str(uuid.uuid4())
            options: list[str] = []
            for letter in "ABCD":
                m = re.search(rf"{letter}\)\s*(.+?)(?:\n|$)", block)
                if m:
                    options.append(m.group(1).strip())
            ans_m = re.search(r"Answer:\s*([A-D])", block, re.IGNORECASE)
            if ans_m:
                answer_keys[q_id] = ans_m.group(1).upper()
            q_text = block.split("\n")[0].strip().lstrip(": ")
            if q_text and options:
                questions.append(Question(
                    id=q_id,
                    text=q_text,
                    question_type="mcq",
                    options=options,
                    topic=topic,
                ))

    session_id = str(uuid.uuid4())
    _quiz_sessions[session_id] = {
        "questions": questions,
        "answer_keys": answer_keys,
        "start_time": datetime.utcnow().isoformat(),
        "time_limit": req.time_limit_seconds,
        "flagged": set(),
    }

    return QuizStartResponse(
        session_id=session_id,
        questions=questions[: req.n_questions],
        time_limit_seconds=req.time_limit_seconds,
    )


@app.post("/quiz/submit", response_model=QuizSubmitResponse)
async def submit_quiz(req: QuizSubmitRequest):
    """Submit quiz answers and get results."""
    from srs.db import log_session, update_topic_mastery

    session = _quiz_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")

    results: list[QuestionResult] = []
    correct_count = 0
    topic_scores: dict[str, list[bool]] = {}
    answer_keys: dict[str, str] = session.get("answer_keys", {})

    # Build per-question lookup
    q_by_id = {q.id: q for q in session["questions"]}

    for answer in req.answers:
        q = q_by_id.get(answer.question_id)
        if q is None:
            continue
        is_correct = False
        explanation = ""
        correct_letter = answer_keys.get(answer.question_id, "")
        if q.options and correct_letter:
            # Match by letter prefix or full option text
            given = answer.answer.strip()
            letter = ""
            if given and given[0].upper() in "ABCD":
                letter = given[0].upper()
            else:
                # Match full text against options
                for i, opt in enumerate(q.options):
                    if opt.strip() == given.strip():
                        letter = "ABCD"[i]
                        break
            is_correct = (letter == correct_letter)
            idx = "ABCD".index(correct_letter) if correct_letter in "ABCD" else 0
            explanation = f"Correct answer: {correct_letter}) {q.options[idx] if idx < len(q.options) else ''}"
        else:
            is_correct = bool(answer.answer.strip())
            explanation = "Self-graded answer."
        correct_count += int(is_correct)

        results.append(QuestionResult(
            question_id=answer.question_id,
            correct=is_correct,
            correct_answer=correct_letter or "",
            explanation=explanation,
        ))
        topic_scores.setdefault(q.topic, []).append(is_correct)

    score = correct_count / max(len(req.answers), 1)
    weak_topics = [t for t, s in topic_scores.items() if (sum(s) / len(s)) < 0.6]

    # Persist mastery + session
    for topic, scs in topic_scores.items():
        if topic:
            update_topic_mastery(topic, sum(scs) / len(scs))
    started = session.get("start_time")
    duration = 0
    if started:
        try:
            duration = int((datetime.utcnow() - datetime.fromisoformat(started)).total_seconds())
        except Exception:
            duration = 0
    log_session(
        kind="quiz",
        topic=", ".join(t for t in topic_scores.keys() if t)[:120] or None,
        duration_seconds=duration,
        score=score,
        impact_score=round(score * 100 - 50, 1),
    )

    return QuizSubmitResponse(
        score=score,
        breakdown=results,
        weak_topics=weak_topics,
    )


@app.post("/quiz/hint", response_model=QuizHintResponse)
async def quiz_hint(req: QuizHintRequest):
    """Get an AI hint for a quiz question without revealing the answer."""
    session = _quiz_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    q = next((qq for qq in session["questions"] if qq.id == req.question_id), None)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")

    engine = get_engine()
    system = (
        "You are a Socratic tutor. Provide a single concise hint (under 50 words) "
        "that nudges the student toward the answer WITHOUT revealing it directly. "
        "Reference relevant concepts to consider."
    )
    prompt = f"Topic: {q.topic}\nQuestion: {q.text}"
    result = engine.generate(prompt=prompt, system_prompt=system, temperature=0.5, max_tokens=200)
    return QuizHintResponse(hint=result["text"])


@app.post("/quiz/flag", response_model=QuizFlagResponse)
async def quiz_flag(req: QuizFlagRequest):
    """Flag/unflag a quiz question for later review."""
    session = _quiz_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    flagged: set = session.setdefault("flagged", set())
    if req.flagged:
        flagged.add(req.question_id)
    else:
        flagged.discard(req.question_id)
    return QuizFlagResponse(flagged_ids=sorted(flagged))


# ── Flashcards ──────────────────────────────────────────

@app.get("/flashcards/due", response_model=FlashcardsDueResponse)
async def get_due_flashcards():
    from srs.db import get_due_cards
    cards = get_due_cards(limit=50)
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
    from srs.scheduler import review_card
    from srs.db import log_session
    schedule = review_card(req.card_id, req.quality)
    log_session(kind="flashcards", duration_seconds=0, score=float(req.quality) / 5.0)
    return FlashcardReviewResponse(
        interval_days=schedule["interval_days"],
        ease_factor=schedule["ease_factor"],
        next_review_at=schedule["next_review_at"],
    )


@app.post("/flashcards/undo", response_model=UndoReviewResponse)
async def undo_review(req: UndoReviewRequest):
    """Undo the most recent review for a card."""
    from srs.db import delete_last_review
    return UndoReviewResponse(undone=delete_last_review(req.card_id))


# ── Progress / Dashboard ────────────────────────────────

@app.get("/progress", response_model=ProgressResponse)
async def get_progress():
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


def _letter_grade(score: Optional[float]) -> str:
    if score is None:
        return "—"
    pct = score * 100
    for cutoff, letter in [(97, "A+"), (93, "A"), (90, "A-"),
                            (87, "B+"), (83, "B"), (80, "B-"),
                            (77, "C+"), (73, "C"), (70, "C-"),
                            (60, "D"), (0, "F")]:
        if pct >= cutoff:
            return letter
    return "F"


@app.get("/dashboard", response_model=DashboardMetrics)
async def dashboard_metrics():
    """Aggregated metrics for the Progress dashboard."""
    from srs.db import (
        get_total_study_seconds, get_avg_quiz_score, get_card_count,
    )
    total_seconds = get_total_study_seconds()
    week_seconds = get_total_study_seconds(days=7)
    weekly_goal_seconds = int(os.getenv("WEEKLY_GOAL_HOURS", "10")) * 3600
    goal_pct = min(100.0, (week_seconds / max(weekly_goal_seconds, 1)) * 100)
    avg_quiz = get_avg_quiz_score(limit=12)

    # Flashcard mastery = portion of cards with ease_factor > 2.5 from latest review
    from srs.db import get_connection
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
        mastered_row = conn.execute(
            """SELECT COUNT(*) c FROM cards c
               WHERE EXISTS (
                 SELECT 1 FROM reviews r
                 WHERE r.card_id = c.id AND r.ease_factor > 2.5
                 ORDER BY r.reviewed_at DESC LIMIT 1
               )"""
        ).fetchone()["c"]
        due_row = conn.execute(
            """SELECT COUNT(*) c FROM cards c
               LEFT JOIN (
                 SELECT card_id, MAX(reviewed_at) m, next_review_at
                 FROM reviews GROUP BY card_id
               ) r ON c.id = r.card_id
               WHERE r.next_review_at IS NULL OR r.next_review_at <= datetime('now')"""
        ).fetchone()["c"]
    retention = (mastered_row / total) if total else 0.0

    return DashboardMetrics(
        study_hours_total=round(total_seconds / 3600, 1),
        study_hours_week=round(week_seconds / 3600, 1),
        weekly_goal_percent=round(goal_pct, 1),
        flashcard_retention=round(retention, 3),
        review_due_count=int(due_row),
        mastered_count=int(mastered_row),
        quiz_avg_score=round(avg_quiz, 3) if avg_quiz is not None else None,
        quiz_letter_grade=_letter_grade(avg_quiz),
    )


@app.get("/sessions/recent", response_model=RecentSessionsResponse)
async def recent_sessions(limit: int = 10):
    from srs.db import get_recent_sessions
    rows = get_recent_sessions(limit=limit)
    return RecentSessionsResponse(sessions=[RecentSession(**r) for r in rows])


@app.post("/sessions", response_model=LogSessionResponse)
async def log_session_endpoint(req: LogSessionRequest):
    from srs.db import log_session
    sid = log_session(
        kind=req.kind, topic=req.topic, duration_seconds=req.duration_seconds,
        score=req.score, impact_score=req.impact_score,
    )
    return LogSessionResponse(id=sid)


@app.get("/activity/heatmap", response_model=HeatmapResponse)
async def activity_heatmap(days: int = 30):
    from srs.db import get_activity_heatmap
    rows = get_activity_heatmap(days=days)
    return HeatmapResponse(days=[HeatmapDay(**r) for r in rows])


# ── Export ──────────────────────────────────────────────

@app.get("/export/anki")
async def export_anki():
    from srs.flashcard_export import export_to_anki
    try:
        path = export_to_anki("Study Companion")
        return FileResponse(
            path, media_type="application/octet-stream",
            filename="study_companion.apkg",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Index Management ────────────────────────────────────

@app.get("/index/files", response_model=IndexFilesResponse)
async def list_index_files():
    """List unique source documents in the index, with chunk counts."""
    retriever = get_retriever()
    counts: dict[str, int] = {}
    for m in getattr(retriever, "metadata", []) or []:
        src = m.get("source", "unknown")
        counts[src] = counts.get(src, 0) + 1
    if not counts:
        for m in getattr(retriever, "bm25_chunks", []) or []:
            src = m.get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
    files = [IndexedFile(source=s, chunk_count=c) for s, c in sorted(counts.items())]
    return IndexFilesResponse(files=files, total_chunks=sum(counts.values()))


@app.delete("/index", response_model=ClearIndexResponse)
async def clear_index():
    """Delete the FAISS / BM25 index and processed chunks."""
    deleted = 0
    retriever = get_retriever()
    deleted = len(getattr(retriever, "metadata", []) or []) or len(getattr(retriever, "bm25_chunks", []) or [])

    for sub in [EMBEDDINGS_DIR, PROCESSED_DIR]:
        if sub.exists():
            try:
                shutil.rmtree(sub)
            except OSError as e:
                raise HTTPException(status_code=500, detail=f"Could not clear {sub}: {e}")
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    global _retriever
    _retriever = None
    return ClearIndexResponse(cleared=True, deleted_chunks=deleted)


# ── Search ──────────────────────────────────────────────

@app.get("/search", response_model=SearchResponse)
async def search_all(q: str, limit: int = 15):
    """Search across indexed chunks and flashcards."""
    from srs.db import search_cards
    q = (q or "").strip()
    if not q:
        return SearchResponse(query=q, hits=[])

    hits: list[SearchHit] = []
    retriever = get_retriever()
    try:
        for r in retriever.search(q, top_k=limit):
            hits.append(SearchHit(
                kind="chunk",
                title=r.get("source", "chunk"),
                snippet=(r.get("text", "")[:240]).strip(),
                score=float(r.get("score", 0.0)),
                extra={"page": r.get("page", 1), "chunk_id": r.get("chunk_id", "")},
            ))
    except Exception:
        pass

    for card in search_cards(q, limit=limit):
        hits.append(SearchHit(
            kind="card",
            title=card["front"][:80],
            snippet=(card["back"] or "")[:240],
            score=0.5,
            extra={"id": card["id"], "topic": card.get("topic")},
        ))

    hits.sort(key=lambda h: h.score, reverse=True)
    return SearchResponse(query=q, hits=hits[:limit])


# ── Bookmarks ───────────────────────────────────────────

@app.get("/bookmarks", response_model=BookmarksResponse)
async def list_bookmarks():
    from srs.db import get_bookmarks
    rows = get_bookmarks(limit=100)
    return BookmarksResponse(bookmarks=[Bookmark(**r) for r in rows])


@app.post("/bookmarks", response_model=Bookmark)
async def create_bookmark(req: BookmarkCreateRequest):
    from srs.db import add_bookmark, get_bookmarks
    bid = add_bookmark(content=req.content, topic=req.topic, mode=req.mode)
    for b in get_bookmarks(limit=5):
        if b["id"] == bid:
            return Bookmark(**b)
    raise HTTPException(status_code=500, detail="Failed to create bookmark")


@app.delete("/bookmarks/{bookmark_id}")
async def remove_bookmark(bookmark_id: str):
    from srs.db import delete_bookmark
    ok = delete_bookmark(bookmark_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}


# ── Health ──────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Never 500 — the entire UI polls this on load."""
    from srs.db import get_card_count

    model_loaded = False
    model_name = ""
    vram = 0.0
    try:
        health = get_engine().health_check()
        model_loaded = health["model_loaded"]
        model_name = health.get("model_name", "")
        vram = health.get("vram_used_gb", 0.0)
    except Exception as e:
        print(f"Engine health failed: {e}", file=sys.stderr)

    index_size = 0
    try:
        index_size = get_retriever().index_size
    except Exception as e:
        print(f"Retriever health failed: {e}", file=sys.stderr)

    try:
        db_cards = get_card_count()
    except Exception:
        db_cards = 0

    return HealthResponse(
        model_loaded=model_loaded,
        model_name=model_name,
        vram_used_gb=vram,
        index_size=index_size,
        db_cards=db_cards,
        status="ok" if model_loaded else "degraded",
    )
