"""Multi-format document ingestion.

Accepts: PDF (text + OCR fallback), DOCX, TXT, MD, image (OCR),
         web URL, YouTube URL, pasted text (stdin).
Returns: List of dicts with keys: source, page, text, lang.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

import requests


def ingest_pdf(path: str) -> list[dict]:
    """Ingest a PDF file. Uses PyMuPDF for text extraction, OCR fallback via pytesseract."""
    import fitz  # pymupdf

    doc = fitz.open(path)
    results = []
    for page_num, page in enumerate(doc, 1):
        text = page.get_text("text").strip()
        # OCR fallback if text extraction yields very little
        if len(text) < 50:
            try:
                import pytesseract
                from PIL import Image
                import io

                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img).strip()
            except Exception:
                pass  # pytesseract may not be installed or configured
        if text:
            results.append({
                "source": os.path.basename(path),
                "page": page_num,
                "text": text,
                "lang": _detect_lang(text),
            })
    doc.close()
    return results


def ingest_docx(path: str) -> list[dict]:
    """Ingest a DOCX file."""
    from docx import Document

    doc = Document(path)
    full_text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    if not full_text.strip():
        return []
    return [{
        "source": os.path.basename(path),
        "page": 1,
        "text": full_text,
        "lang": _detect_lang(full_text),
    }]


def ingest_text(path: str) -> list[dict]:
    """Ingest a plain text or markdown file."""
    text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    return [{
        "source": os.path.basename(path),
        "page": 1,
        "text": text,
        "lang": _detect_lang(text),
    }]


def ingest_image(path: str) -> list[dict]:
    """Ingest an image file via OCR."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(path)
        text = pytesseract.image_to_string(img).strip()
        if text:
            return [{
                "source": os.path.basename(path),
                "page": 1,
                "text": text,
                "lang": _detect_lang(text),
            }]
    except Exception:
        pass
    return []


def ingest_url(url: str) -> list[dict]:
    """Ingest content from a web URL."""
    from bs4 import BeautifulSoup

    resp = requests.get(url, timeout=30, headers={"User-Agent": "StudyCompanion/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script, style, nav elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    if not text:
        return []
    return [{
        "source": url,
        "page": 1,
        "text": text,
        "lang": _detect_lang(text),
    }]


def ingest_youtube(url: str) -> list[dict]:
    """Ingest transcript from a YouTube video URL."""
    from youtube_transcript_api import YouTubeTranscriptApi

    video_id = _extract_youtube_id(url)
    if not video_id:
        return []

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join(entry["text"] for entry in transcript)
        return [{
            "source": f"youtube:{video_id}",
            "page": 1,
            "text": text,
            "lang": _detect_lang(text),
        }]
    except Exception:
        return []


def ingest_stdin() -> list[dict]:
    """Ingest text from stdin (pasted text)."""
    if sys.stdin.isatty():
        return []
    text = sys.stdin.read().strip()
    if not text:
        return []
    return [{
        "source": "stdin",
        "page": 1,
        "text": text,
        "lang": _detect_lang(text),
    }]


def ingest(source: str) -> list[dict]:
    """Auto-detect source type and ingest.

    Args:
        source: File path, URL, or '-' for stdin.

    Returns:
        List of document chunks with source, page, text, lang.
    """
    if source == "-":
        return ingest_stdin()

    # YouTube URL detection
    if re.match(r"https?://(www\.)?(youtube\.com|youtu\.be)/", source):
        return ingest_youtube(source)

    # Web URL detection
    if source.startswith(("http://", "https://")):
        return ingest_url(source)

    # File-based ingestion
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {source}")

    ext = path.suffix.lower()
    if ext == ".pdf":
        return ingest_pdf(source)
    elif ext == ".docx":
        return ingest_docx(source)
    elif ext in (".txt", ".md", ".markdown", ".rst"):
        return ingest_text(source)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"):
        return ingest_image(source)
    else:
        # Try as plain text
        return ingest_text(source)


def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract video ID from a YouTube URL."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _detect_lang(text: str) -> str:
    """Simple language detection heuristic."""
    # Check for common non-ASCII scripts
    sample = text[:500]
    if re.search(r"[\u4e00-\u9fff]", sample):
        return "zh"
    if re.search(r"[\u0900-\u097f]", sample):
        return "hi"
    if re.search(r"[\u0600-\u06ff]", sample):
        return "ar"
    if re.search(r"[\u3040-\u30ff]", sample):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", sample):
        return "ko"
    return "en"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Ingest documents into study companion")
    parser.add_argument("sources", nargs="+", help="File paths, URLs, or '-' for stdin")
    parser.add_argument("--output", "-o", help="Output JSONL file (default: stdout)")
    args = parser.parse_args()

    results = []
    for src in args.sources:
        try:
            docs = ingest(src)
            results.extend(docs)
        except Exception as e:
            print(f"Warning: Failed to ingest {src}: {e}", file=sys.stderr)

    output = "\n".join(json.dumps(r, ensure_ascii=False) for r in results)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Wrote {len(results)} documents to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
