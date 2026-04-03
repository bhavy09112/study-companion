"""Text normalization and cleaning.

Removes: headers/footers/page numbers, watermarks, excessive whitespace, boilerplate.
Normalizes: unicode, ligatures, hyphenation across line breaks.
Preserves: LaTeX math, code blocks, tables.
"""
from __future__ import annotations

import re
import unicodedata


# Common ligature replacements
LIGATURES = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
    "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st",
    "\ufb06": "st",
}

# Patterns for content that should be preserved as-is
LATEX_PATTERN = re.compile(r"(\$\$?.*?\$\$?|\\begin\{.*?\}.*?\\end\{.*?\})", re.DOTALL)
CODE_BLOCK_PATTERN = re.compile(r"(```.*?```|~~~.*?~~~)", re.DOTALL)

# Header/footer patterns
HEADER_FOOTER_PATTERNS = [
    re.compile(r"^(?:Page\s+)?\d+\s*(?:of\s+\d+)?$", re.MULTILINE),
    re.compile(r"^\s*(?:Chapter|Section)\s+\d+\s*$", re.MULTILINE),
    re.compile(r"^(?:All rights reserved|Copyright|©).*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^(?:Confidential|Draft|DRAFT).*$", re.MULTILINE),
]

# Watermark patterns
WATERMARK_PATTERNS = [
    re.compile(r"(?:CONFIDENTIAL|DRAFT|DO NOT DISTRIBUTE|WATERMARK)", re.IGNORECASE),
]


def normalize_unicode(text: str) -> str:
    """Normalize unicode characters and replace ligatures."""
    text = unicodedata.normalize("NFKC", text)
    for lig, replacement in LIGATURES.items():
        text = text.replace(lig, replacement)
    return text


def fix_hyphenation(text: str) -> str:
    """Rejoin words split across line breaks by hyphenation."""
    # Match word-hyphen at end of line followed by continuation
    return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)


def remove_headers_footers(text: str) -> str:
    """Remove common header/footer patterns."""
    for pattern in HEADER_FOOTER_PATTERNS:
        text = pattern.sub("", text)
    return text


def remove_watermarks(text: str) -> str:
    """Remove watermark text."""
    for pattern in WATERMARK_PATTERNS:
        text = pattern.sub("", text)
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse excessive whitespace while preserving paragraph breaks."""
    # Preserve double newlines (paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse spaces/tabs within lines
    text = re.sub(r"[ \t]+", " ", text)
    # Remove trailing whitespace on each line
    text = re.sub(r" +\n", "\n", text)
    return text.strip()


def _protect_special_content(text: str) -> tuple[str, dict[str, str]]:
    """Replace LaTeX and code blocks with placeholders to protect them during cleaning."""
    placeholders: dict[str, str] = {}
    counter = 0

    for pattern in [LATEX_PATTERN, CODE_BLOCK_PATTERN]:
        for match in pattern.finditer(text):
            key = f"__PROTECTED_{counter}__"
            placeholders[key] = match.group(0)
            text = text.replace(match.group(0), key, 1)
            counter += 1

    return text, placeholders


def _restore_special_content(text: str, placeholders: dict[str, str]) -> str:
    """Restore protected LaTeX and code blocks."""
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def clean_text(text: str) -> str:
    """Apply full cleaning pipeline to a text string.

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned and normalized text.
    """
    # Protect special content
    text, placeholders = _protect_special_content(text)

    # Apply cleaning steps
    text = normalize_unicode(text)
    text = fix_hyphenation(text)
    text = remove_headers_footers(text)
    text = remove_watermarks(text)
    text = normalize_whitespace(text)

    # Restore protected content
    text = _restore_special_content(text, placeholders)

    return text


def clean_documents(documents: list[dict]) -> list[dict]:
    """Clean a list of ingested documents.

    Args:
        documents: List of dicts from ingest.py.

    Returns:
        Same list with cleaned text field.
    """
    cleaned = []
    for doc in documents:
        cleaned_text = clean_text(doc["text"])
        if cleaned_text:  # Skip empty documents
            cleaned.append({**doc, "text": cleaned_text})
    return cleaned


if __name__ == "__main__":
    import json
    import sys

    # Read JSONL from stdin or file
    if len(sys.argv) > 1:
        from pathlib import Path
        lines = Path(sys.argv[1]).read_text(encoding="utf-8").strip().split("\n")
    else:
        lines = sys.stdin.read().strip().split("\n")

    docs = [json.loads(line) for line in lines if line.strip()]
    cleaned = clean_documents(docs)

    for doc in cleaned:
        print(json.dumps(doc, ensure_ascii=False))
