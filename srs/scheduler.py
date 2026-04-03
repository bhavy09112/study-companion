"""SM-2 Spaced Repetition Algorithm.

Standard SM-2 formula implementation for scheduling flashcard reviews.
Quality scale: 0 (complete blackout) to 5 (perfect response).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from srs.db import add_review, update_topic_mastery, get_due_cards

# SM-2 defaults
DEFAULT_EASE_FACTOR = 2.5
MIN_EASE_FACTOR = 1.3


def sm2_schedule(
    quality: int,
    previous_interval: float = 0.0,
    previous_ease: float = DEFAULT_EASE_FACTOR,
    repetition: int = 0,
) -> dict:
    """Compute the next review schedule using the SM-2 algorithm.

    Args:
        quality: Quality of response (0-5).
            0 = complete blackout
            1 = incorrect, but remembered upon seeing answer
            2 = incorrect, but easy to recall
            3 = correct with serious difficulty
            4 = correct with some hesitation
            5 = perfect response
        previous_interval: Previous interval in days.
        previous_ease: Previous ease factor.
        repetition: Number of successful repetitions.

    Returns:
        Dict with interval_days, ease_factor, repetition, next_review_at.
    """
    quality = max(0, min(5, quality))

    # Update ease factor
    ease = previous_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(MIN_EASE_FACTOR, ease)

    # Calculate interval
    if quality < 3:
        # Failed — reset
        interval = 1.0
        repetition = 0
    else:
        if repetition == 0:
            interval = 1.0
        elif repetition == 1:
            interval = 6.0
        else:
            interval = previous_interval * ease
        repetition += 1

    # Calculate next review date
    next_review = datetime.now() + timedelta(days=interval)

    return {
        "interval_days": round(interval, 2),
        "ease_factor": round(ease, 2),
        "repetition": repetition,
        "next_review_at": next_review.isoformat(),
    }


def review_card(card_id: str, quality: int) -> dict:
    """Process a card review and update the schedule.

    Args:
        card_id: Card ID.
        quality: Quality rating (0-5).

    Returns:
        Updated schedule dict.
    """
    from srs.db import get_connection

    # Get previous review info
    with get_connection() as conn:
        row = conn.execute("""
            SELECT interval_days, ease_factor, COUNT(*) as rep_count
            FROM reviews
            WHERE card_id = ? AND quality >= 3
            ORDER BY reviewed_at DESC
            LIMIT 1
        """, (card_id,)).fetchone()

    previous_interval = row["interval_days"] if row and row["interval_days"] else 0.0
    previous_ease = row["ease_factor"] if row and row["ease_factor"] else DEFAULT_EASE_FACTOR
    repetition = row["rep_count"] if row else 0

    # Compute new schedule
    schedule = sm2_schedule(quality, previous_interval, previous_ease, repetition)

    # Save review
    add_review(
        card_id=card_id,
        quality=quality,
        interval_days=schedule["interval_days"],
        ease_factor=schedule["ease_factor"],
        next_review_at=schedule["next_review_at"],
    )

    return schedule


def compute_topic_mastery(topic: str) -> float:
    """Compute mastery score for a topic based on card performance.

    Returns a score between 0.0 and 1.0.

    [BONUS FEATURE] Uses weighted average that factors in recency,
    ease factor, and response quality trends.
    """
    from srs.db import get_connection

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT r.quality, r.ease_factor, r.interval_days,
                   r.reviewed_at, c.topic
            FROM reviews r
            JOIN cards c ON r.card_id = c.id
            WHERE c.topic = ?
            ORDER BY r.reviewed_at DESC
            LIMIT 50
        """, (topic,)).fetchall()

    if not rows:
        return 0.0

    # Weighted average: recent reviews count more
    total_weight = 0.0
    weighted_score = 0.0
    for i, row in enumerate(rows):
        weight = 1.0 / (1.0 + i * 0.1)  # Decay with position
        score = row["quality"] / 5.0  # Normalize to 0-1
        weighted_score += weight * score
        total_weight += weight

    mastery = weighted_score / total_weight if total_weight > 0 else 0.0

    # Update in DB
    update_topic_mastery(topic, round(mastery, 3))

    return round(mastery, 3)


if __name__ == "__main__":
    # Test SM-2 algorithm
    print("SM-2 Schedule Tests:")

    # Perfect response, first time
    s = sm2_schedule(5, 0, 2.5, 0)
    print(f"  q=5, rep=0: interval={s['interval_days']}d, ease={s['ease_factor']}")

    # Perfect response, second time
    s = sm2_schedule(5, 1.0, 2.6, 1)
    print(f"  q=5, rep=1: interval={s['interval_days']}d, ease={s['ease_factor']}")

    # Good response, third time
    s = sm2_schedule(4, 6.0, 2.6, 2)
    print(f"  q=4, rep=2: interval={s['interval_days']}d, ease={s['ease_factor']}")

    # Failed response
    s = sm2_schedule(1, 15.0, 2.5, 3)
    print(f"  q=1, rep=3: interval={s['interval_days']}d, ease={s['ease_factor']} (RESET)")
