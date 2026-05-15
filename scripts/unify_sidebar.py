"""Replace the sidebar in every web/*.html with one canonical sidebar.

The Stitch exports each shipped a slightly different sidebar (nav vs aside,
ul vs div, different brand mark). This rewrites all 5 to an identical block,
flipping only the active nav item per page. Idempotent.
"""
from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

PAGES = {
    "index.html": "study",
    "quiz.html": "quiz",
    "flashcards.html": "flashcards",
    "progress.html": "progress",
    "settings.html": "settings",
}

NAV = [
    ("study",      "/",             "book_2",    "Study"),
    ("quiz",       "/quiz",         "quiz",      "Quiz"),
    ("flashcards", "/flashcards",   "style",     "Flashcards"),
    ("progress",   "/progress-page","analytics", "Progress"),
    ("settings",   "/settings",     "settings",  "Settings"),
]

START = "<!-- SC_SIDEBAR_START -->"
END = "<!-- SC_SIDEBAR_END -->"


def build_sidebar(active: str) -> str:
    links = []
    for nid, href, icon, label in NAV:
        if nid == active:
            links.append(
                f'<a class="flex items-center gap-sm px-sm py-[8px] rounded-lg '
                f'text-primary font-bold border-r-2 border-primary '
                f'bg-surface-container-high transition-all" href="{href}">'
                f'<span class="material-symbols-outlined icon-fill" '
                f'style="font-variation-settings:\'FILL\' 1;">{icon}</span>'
                f'<span class="font-label-md text-label-md">{label}</span></a>'
            )
        else:
            links.append(
                f'<a class="flex items-center gap-sm px-sm py-[8px] rounded-lg '
                f'text-on-surface-variant hover:text-primary '
                f'hover:bg-surface-container-low transition-colors duration-200" '
                f'href="{href}">'
                f'<span class="material-symbols-outlined">{icon}</span>'
                f'<span class="font-label-md text-label-md">{label}</span></a>'
            )
    nav_links = "\n".join(links)
    return f"""{START}
<nav class="bg-surface h-screen w-64 fixed left-0 top-0 border-r border-outline-variant flex flex-col py-md px-sm z-50">
<a href="/" class="flex items-center gap-xs px-xs mb-lg" style="text-decoration:none;">
<div class="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-on-primary font-bold">SC</div>
<div>
<h1 class="font-headline-lg text-primary text-[16px] leading-[20px] m-0 font-bold">Study Companion</h1>
<p class="font-label-sm text-label-sm text-on-surface-variant m-0 uppercase tracking-wider">AI Assistant</p>
</div>
</a>
<button class="bg-primary text-on-primary font-label-md text-label-md rounded-lg py-xs px-sm mb-lg flex items-center justify-center gap-xs hover:bg-primary-container transition-colors duration-200 w-full">
<span class="material-symbols-outlined text-[18px]">upload_file</span>
Upload Document
</button>
<div class="flex-grow flex flex-col gap-base">
{nav_links}
</div>
<div class="border-t border-outline-variant pt-sm mt-sm">
<a class="flex items-center gap-sm px-sm py-[8px] rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-low transition-colors duration-200" href="/progress-page">
<span class="material-symbols-outlined">monitor_heart</span>
<span class="font-label-md text-label-md">System Health</span>
</a>
</div>
</nav>
{END}"""


def find_sidebar_span(html: str) -> tuple[int, int] | None:
    """Return (start, end) covering the sidebar element (nav or aside)."""
    # Already wired? Replace between markers.
    if START in html and END in html:
        s = html.index(START)
        e = html.index(END) + len(END)
        return (s, e)

    # Find the opening tag of the element that carries the sidebar layout.
    m = re.search(r'<(nav|aside)\b[^>]*\bw-64\b[^>]*\bfixed\b[^>]*>', html)
    if not m:
        m = re.search(r'<(nav|aside)\b[^>]*\bfixed\b[^>]*\bleft-0\b[^>]*>', html)
    if not m:
        return None
    tag = m.group(1)
    start = m.start()

    # Balanced scan for the matching close tag of the SAME tag name.
    depth = 0
    for tm in re.finditer(rf'<(/?){tag}\b', html[start:]):
        if tm.group(1) == "":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                close = re.search(rf'</{tag}\s*>', html[start + tm.start():])
                end = start + tm.start() + close.end()
                return (start, end)
    return None


def main():
    for filename, active in PAGES.items():
        path = WEB / filename
        if not path.exists():
            print(f"skip (missing): {filename}")
            continue
        html = path.read_text(encoding="utf-8")
        span = find_sidebar_span(html)
        if not span:
            print(f"!! sidebar not found in {filename}")
            continue
        s, e = span
        new_html = html[:s] + build_sidebar(active) + html[e:]
        path.write_text(new_html, encoding="utf-8")
        print(f"unified sidebar in {filename} (active={active})")


if __name__ == "__main__":
    main()
