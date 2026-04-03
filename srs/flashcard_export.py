"""Anki APKG flashcard export using genanki.

Creates proper .apkg decks with source citations in notes.
"""
from __future__ import annotations

import hashlib
import os
import random
from pathlib import Path
from typing import Optional

import genanki

from srs.db import get_all_cards

# Stable model and deck IDs (derived from name hash for consistency)
MODEL_ID = int(hashlib.md5(b"StudyCompanionModel").hexdigest()[:8], 16)
DECK_ID = int(hashlib.md5(b"StudyCompanionDeck").hexdigest()[:8], 16)

# Anki note model
STUDY_MODEL = genanki.Model(
    MODEL_ID,
    "Study Companion Card",
    fields=[
        {"name": "Front"},
        {"name": "Back"},
        {"name": "Source"},
        {"name": "Topic"},
    ],
    templates=[
        {
            "name": "Study Card",
            "qfmt": """
                <div class="front">{{Front}}</div>
                <div class="topic" style="font-size: 0.8em; color: #666; margin-top: 10px;">
                    Topic: {{Topic}}
                </div>
            """,
            "afmt": """
                {{FrontSide}}
                <hr id="answer">
                <div class="back">{{Back}}</div>
                <div class="source" style="font-size: 0.7em; color: #999; margin-top: 10px;">
                    Source: {{Source}}
                </div>
            """,
        },
    ],
    css="""
        .card {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 16px;
            text-align: left;
            color: #333;
            background-color: #fff;
            padding: 20px;
        }
        .front { font-size: 1.2em; font-weight: bold; }
        .back { line-height: 1.6; }
    """,
)


def export_to_anki(
    deck_name: str = "Study Companion",
    output_path: Optional[str] = None,
    cards: Optional[list[dict]] = None,
) -> str:
    """Export flashcards to an Anki .apkg file.

    Args:
        deck_name: Name of the Anki deck.
        output_path: Output file path. Defaults to data/exports/{deck_name}.apkg.
        cards: Cards to export. If None, exports all cards from DB.

    Returns:
        Path to the exported .apkg file.
    """
    if cards is None:
        cards = get_all_cards()

    if not cards:
        raise ValueError("No cards to export")

    # Create deck
    deck = genanki.Deck(DECK_ID, deck_name)

    for card in cards:
        note = genanki.Note(
            model=STUDY_MODEL,
            fields=[
                card.get("front") or "",
                card.get("back") or "",
                card.get("source_chunk_id") or "N/A",
                card.get("topic") or "General",
            ],
        )
        deck.add_note(note)

    # Determine output path
    if output_path is None:
        export_dir = Path("data/exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        safe_name = deck_name.replace(" ", "_").lower()
        output_path = str(export_dir / f"{safe_name}.apkg")

    # Package and save
    package = genanki.Package(deck)
    package.write_to_file(output_path)

    print(f"Exported {len(cards)} cards to {output_path}")
    return output_path


def generate_flashcards_from_chunks(
    chunks: list[dict],
    topic: Optional[str] = None,
) -> list[dict]:
    """Generate flashcard front/back pairs from text chunks.

    [BONUS FEATURE] Auto-generates flashcards from study material.

    Args:
        chunks: List of chunk dicts with 'text' key.
        topic: Topic name for the cards.

    Returns:
        List of card dicts with front, back, source_chunk_id, topic.
    """
    cards = []
    for chunk in chunks:
        text = chunk.get("text", "")
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line or len(line) < 20:
                continue

            # Pattern: "Term: Definition" or "Term - Definition"
            for sep in [":", " - ", " – "]:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2 and len(parts[0]) < 100 and len(parts[1]) > 10:
                        cards.append({
                            "front": f"Define: {parts[0].strip().lstrip('0123456789.-) ')}",
                            "back": parts[1].strip(),
                            "source_chunk_id": chunk.get("chunk_id", ""),
                            "topic": topic or "General",
                        })
                        break

    return cards


if __name__ == "__main__":
    # Test with existing DB cards
    from srs.db import init_db, add_card

    init_db()
    # Add a test card if none exist
    add_card("What is the Calvin Cycle?",
             "A cycle of chemical reactions in the stroma of chloroplasts that fixes CO2 into glucose.",
             topic="Biology")

    path = export_to_anki("Test Deck")
    print(f"Export test: {path}")
