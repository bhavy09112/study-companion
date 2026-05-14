"""SQLite database for spaced repetition system.

Schema: cards, reviews, topics tables.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DB_PATH = os.getenv("SRS_DB_PATH", "data/srs.db")


def get_db_path() -> str:
    """Get the database path, creating parent dirs if needed."""
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database schema."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                source_chunk_id TEXT,
                topic TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                card_id TEXT NOT NULL,
                reviewed_at TEXT NOT NULL DEFAULT (datetime('now')),
                quality INTEGER NOT NULL CHECK (quality >= 0 AND quality <= 5),
                interval_days REAL NOT NULL,
                ease_factor REAL NOT NULL,
                next_review_at TEXT NOT NULL,
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS topics (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                mastery_score REAL NOT NULL DEFAULT 0.0,
                last_studied_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                topic TEXT,
                kind TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                score REAL,
                impact_score REAL,
                started_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS bookmarks (
                id TEXT PRIMARY KEY,
                topic TEXT,
                mode TEXT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews(card_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_next ON reviews(next_review_at);
            CREATE INDEX IF NOT EXISTS idx_cards_topic ON cards(topic);
            CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
        """)


def add_card(
    front: str,
    back: str,
    source_chunk_id: Optional[str] = None,
    topic: Optional[str] = None,
) -> str:
    """Add a new flashcard.

    Args:
        front: Question/front of card.
        back: Answer/back of card.
        source_chunk_id: Reference to source chunk.
        topic: Topic name.

    Returns:
        Card ID.
    """
    card_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO cards (id, front, back, source_chunk_id, topic) VALUES (?, ?, ?, ?, ?)",
            (card_id, front, back, source_chunk_id, topic),
        )
        # Ensure topic exists
        if topic:
            conn.execute(
                "INSERT OR IGNORE INTO topics (id, name) VALUES (?, ?)",
                (str(uuid.uuid4()), topic),
            )
    return card_id


def get_due_cards(limit: int = 20) -> list[dict]:
    """Get cards that are due for review.

    Args:
        limit: Maximum number of cards to return.

    Returns:
        List of card dicts.
    """
    now = datetime.now(tz=None).isoformat()
    with get_connection() as conn:
        # Cards with no reviews (new cards) or cards past their review date
        rows = conn.execute("""
            SELECT c.id, c.front, c.back, c.source_chunk_id, c.topic, c.created_at,
                   r.next_review_at, r.ease_factor, r.interval_days
            FROM cards c
            LEFT JOIN (
                SELECT card_id, next_review_at, ease_factor, interval_days,
                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY reviewed_at DESC) as rn
                FROM reviews
            ) r ON c.id = r.card_id AND r.rn = 1
            WHERE r.next_review_at IS NULL OR r.next_review_at <= ?
            ORDER BY r.next_review_at ASC NULLS FIRST
            LIMIT ?
        """, (now, limit)).fetchall()

    return [dict(row) for row in rows]


def add_review(
    card_id: str,
    quality: int,
    interval_days: float,
    ease_factor: float,
    next_review_at: str,
) -> str:
    """Record a review for a card.

    Args:
        card_id: Card ID.
        quality: SM-2 quality rating (0-5).
        interval_days: Computed interval until next review.
        ease_factor: Updated ease factor.
        next_review_at: ISO timestamp of next review.

    Returns:
        Review ID.
    """
    review_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO reviews (id, card_id, quality, interval_days, ease_factor, next_review_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (review_id, card_id, quality, interval_days, ease_factor, next_review_at),
        )
    return review_id


def get_card_count() -> int:
    """Get total number of cards."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM cards").fetchone()
        return row["cnt"]


def get_topic_progress() -> list[dict]:
    """Get mastery progress for all topics."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT t.name, t.mastery_score, t.last_studied_at,
                   COUNT(c.id) as card_count,
                   COALESCE(AVG(r.quality), 0) as avg_quality
            FROM topics t
            LEFT JOIN cards c ON c.topic = t.name
            LEFT JOIN (
                SELECT card_id, quality,
                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY reviewed_at DESC) as rn
                FROM reviews
            ) r ON c.id = r.card_id AND r.rn = 1
            GROUP BY t.id
            ORDER BY t.name
        """).fetchall()

    return [dict(row) for row in rows]


def update_topic_mastery(topic_name: str, mastery_score: float) -> None:
    """Update mastery score for a topic."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE topics SET mastery_score = ?, last_studied_at = datetime('now')
               WHERE name = ?""",
            (mastery_score, topic_name),
        )


def get_all_cards() -> list[dict]:
    """Get all cards for export."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, front, back, source_chunk_id, topic, created_at FROM cards"
        ).fetchall()
    return [dict(row) for row in rows]


def delete_card(card_id: str) -> bool:
    """Delete a card and its reviews. Returns True if deleted."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        return cur.rowcount > 0


def last_review(card_id: str) -> Optional[dict]:
    """Return the most recent review for a card, or None."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT id, card_id, reviewed_at, quality, interval_days, ease_factor, next_review_at
               FROM reviews WHERE card_id = ?
               ORDER BY reviewed_at DESC LIMIT 1""",
            (card_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_last_review(card_id: str) -> bool:
    """Remove the most recent review for a card (Undo support). Returns True if removed."""
    last = last_review(card_id)
    if not last:
        return False
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM reviews WHERE id = ?", (last["id"],))
        return cur.rowcount > 0


# ── Sessions ────────────────────────────────────────────

def log_session(
    kind: str,
    topic: Optional[str] = None,
    duration_seconds: int = 0,
    score: Optional[float] = None,
    impact_score: Optional[float] = None,
) -> str:
    """Record a study/quiz/flashcard session."""
    sid = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO sessions (id, topic, kind, duration_seconds, score, impact_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sid, topic, kind, duration_seconds, score, impact_score),
        )
    return sid


def get_recent_sessions(limit: int = 10) -> list[dict]:
    """Get most recent sessions."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, topic, kind, duration_seconds, score, impact_score, started_at
               FROM sessions ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_activity_heatmap(days: int = 30) -> list[dict]:
    """Get per-day session counts and total duration for the last N days."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT date(started_at) as day,
                      COUNT(*) as count,
                      COALESCE(SUM(duration_seconds), 0) as duration
               FROM sessions
               WHERE started_at >= date('now', ?)
               GROUP BY day
               ORDER BY day""",
            (f"-{int(days)} days",),
        ).fetchall()
    return [dict(row) for row in rows]


def get_total_study_seconds(days: Optional[int] = None) -> int:
    """Total study time. Pass days=N to limit to last N days."""
    with get_connection() as conn:
        if days is None:
            row = conn.execute(
                "SELECT COALESCE(SUM(duration_seconds), 0) as total FROM sessions"
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT COALESCE(SUM(duration_seconds), 0) as total FROM sessions
                   WHERE started_at >= date('now', ?)""",
                (f"-{int(days)} days",),
            ).fetchone()
    return int(row["total"])


def get_avg_quiz_score(limit: int = 12) -> Optional[float]:
    """Mean score across the last N quiz sessions, or None."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT score FROM sessions
               WHERE kind = 'quiz' AND score IS NOT NULL
               ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    scores = [r["score"] for r in rows]
    return sum(scores) / len(scores) if scores else None


# ── Bookmarks ───────────────────────────────────────────

def add_bookmark(content: str, topic: Optional[str] = None, mode: Optional[str] = None) -> str:
    """Save a generated output for later."""
    bid = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO bookmarks (id, topic, mode, content) VALUES (?, ?, ?, ?)",
            (bid, topic, mode, content),
        )
    return bid


def get_bookmarks(limit: int = 50) -> list[dict]:
    """List bookmarks."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, topic, mode, content, created_at FROM bookmarks "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_bookmark(bookmark_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        return cur.rowcount > 0


# ── Search ──────────────────────────────────────────────

def search_cards(query: str, limit: int = 20) -> list[dict]:
    """Simple LIKE-based search across card front/back/topic."""
    q = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, front, back, topic, created_at FROM cards
               WHERE front LIKE ? OR back LIKE ? OR topic LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (q, q, q, limit),
        ).fetchall()
    return [dict(row) for row in rows]


# Initialize on import
init_db()


if __name__ == "__main__":
    init_db()
    cid = add_card("What is photosynthesis?", "The process of converting light energy to chemical energy.", topic="Biology")
    print(f"Added card: {cid}")
    print(f"Due cards: {len(get_due_cards())}")
    print(f"Total cards: {get_card_count()}")
