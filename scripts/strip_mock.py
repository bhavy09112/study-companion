"""Replace hardcoded Stitch demo values with neutral empty states.

The per-page JS fills real data from the API, but the static markup still
ships fake numbers/text that flash on first paint (or linger if the API is
slow). This swaps them for zeros / dashes / short how-to notes. Idempotent.
"""
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "quiz.html": [
        ("Topic: Advanced Cellular Biology",
         "Set topics and difficulty, then start a quiz"),
        ("Question 4 of 15", "Question 0 of 0"),
        (">12:45<", ">00:00<"),
        (">100%<", ">0%<"),
        (">~8 mins<", ">&mdash;<"),
        ("Recall the chemiosmotic theory proposed by Peter Mitchell. "
         "Consider what the complexes in the membrane are actually moving, "
         "and what happens when they build up on one side.",
         "Hints appear here. Press “Hint” on a question for a "
         "Socratic nudge from the AI tutor — it points you toward the "
         "answer without giving it away."),
    ],
    "flashcards.html": [
        (">Neurobiology 301<", ">All Cards<"),
        ('font-bold">42<', 'font-bold">0<'),
        (">Card 12 of 42<", ">Card 0 of 0<"),
    ],
    "progress.html": [
        ('text-primary mb-1">42.5<', 'text-primary mb-1">0.0<'),
        ('text-primary mb-1">91<', 'text-primary mb-1">0<'),
        ('text-primary mb-1">B+<', 'text-primary mb-1">&mdash;<'),
        (">Cognitive-4o-Turbo<", ">&mdash;<"),
        ('font-medium">14,204<', 'font-medium">0<'),
        (">2 mins ago<", ">&mdash;<"),
        ("+5.2 hrs this week", "Upload material and start studying"),
        ("Retention rate across 4 decks", "No reviews recorded yet"),
        ("Based on last 12 assessments", "Take a quiz to start tracking"),
    ],
    "settings.html": [
        (">1.2 GB / 5 GB<", ">0 chunks<"),
    ],
}


def main():
    for filename, pairs in REPLACEMENTS.items():
        path = WEB / filename
        if not path.exists():
            print(f"skip (missing): {filename}")
            continue
        html = path.read_text(encoding="utf-8")
        changed = 0
        for old, new in pairs:
            if old in html:
                html = html.replace(old, new)
                changed += 1
        path.write_text(html, encoding="utf-8")
        print(f"{filename}: {changed}/{len(pairs)} replacements applied")


if __name__ == "__main__":
    main()
