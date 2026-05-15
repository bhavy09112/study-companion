"""Surgically wire Stitch HTML files for backend use.

What this does (idempotent):
    1. Rewrites nav href="#" links to real routes based on the visible link text.
    2. Appends <script> tags before </body> if not already present.

It does NOT modify visible markup, classes, copy, or structure.
"""
from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

NAV_ROUTES = {
    "Study": "/",
    "Quiz": "/quiz",
    "Flashcards": "/flashcards",
    "Progress": "/progress-page",
    "Settings": "/settings",
    "System Health": "/progress-page",
}

# Each page loads api.js + hooks.js + a page-specific script.
PAGE_SCRIPTS = {
    "index.html":      ["/static/api.js", "/static/hooks.js", "/static/study.js"],
    "quiz.html":       ["/static/api.js", "/static/hooks.js", "/static/quiz.js"],
    "flashcards.html": ["/static/api.js", "/static/hooks.js", "/static/flashcards.js"],
    "progress.html":   ["/static/api.js", "/static/hooks.js", "/static/progress.js"],
    "settings.html":   ["/static/api.js", "/static/hooks.js", "/static/settings.js"],
}

PAGE_TO_ID = {
    "index.html": "study",
    "quiz.html": "quiz",
    "flashcards.html": "flashcards",
    "progress.html": "progress",
    "settings.html": "settings",
}


def rewrite_nav_hrefs(html: str) -> str:
    """Replace href="#" with real routes by inspecting the link's visible label."""
    # Match <a ... href="#" ...>...</a> blocks
    pattern = re.compile(r'(<a\b[^>]*?\bhref=")(#)("[^>]*>)(.*?)(</a>)', re.DOTALL)

    def repl(m):
        opener, _hash, attrs_end, inner, closer = m.groups()
        # Find a label by stripping tags and whitespace
        text = re.sub(r"<[^>]+>", " ", inner)
        text = " ".join(text.split())
        for label, route in NAV_ROUTES.items():
            if label.lower() in text.lower():
                return f'{opener}{route}{attrs_end}{inner}{closer}'
        return m.group(0)  # leave non-nav anchors alone

    return pattern.sub(repl, html)


def inject_scripts(html: str, scripts: list[str], page_id: str) -> str:
    """Insert script tags + a data-page attribute on <body>, idempotently."""
    # Add data-page to <body>
    html = re.sub(
        r"<body\b([^>]*)>",
        lambda m: (
            f"<body{m.group(1)}>" if 'data-page=' in m.group(1)
            else f'<body data-page="{page_id}"{m.group(1)}>'
        ),
        html, count=1,
    )

    # Insert scripts before </body>, skipping any already present
    new_tags = []
    for src in scripts:
        if f'src="{src}"' not in html:
            new_tags.append(f'<script src="{src}"></script>')
    if new_tags:
        injected = "\n" + "\n".join(new_tags) + "\n"
        html = html.replace("</body>", injected + "</body>", 1)
    return html


def main():
    for filename, scripts in PAGE_SCRIPTS.items():
        path = WEB / filename
        if not path.exists():
            print(f"skip (missing): {filename}")
            continue
        html = path.read_text(encoding="utf-8")
        before_len = len(html)
        html = rewrite_nav_hrefs(html)
        html = inject_scripts(html, scripts, PAGE_TO_ID[filename])
        path.write_text(html, encoding="utf-8")
        print(f"wired {filename}: {before_len} -> {len(html)} bytes")


if __name__ == "__main__":
    main()
