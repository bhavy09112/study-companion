"""Semantic chunking with sliding-window fallback.

Strategy: Split on topic shifts (double newlines, heading patterns) first.
Fallback: Sliding window with configurable size and overlap.
Output: List of dicts with chunk_id, source, text, tokens.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Approximate token count: ~4 chars per token for English
CHARS_PER_TOKEN = 4

# Default chunking parameters
DEFAULT_CHUNK_SIZE = 512  # tokens
DEFAULT_OVERLAP = 64      # tokens
MIN_CHUNK_SIZE = 50       # tokens — discard chunks shorter than this


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def generate_chunk_id(source: str, index: int, text: str) -> str:
    """Generate a deterministic chunk ID."""
    content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return f"{source}::chunk_{index}::{content_hash}"


def semantic_split(text: str) -> list[str]:
    """Split text on semantic boundaries (headings, double newlines, topic shifts).

    [BONUS FEATURE] Also detects numbered/bulleted list boundaries and
    keeps list items together with their header.
    """
    # Split on double newlines (paragraph boundaries)
    paragraphs = re.split(r"\n{2,}", text)

    # Further split on heading-like patterns within paragraphs
    segments = []
    for para in paragraphs:
        # Check for heading patterns (e.g., "1. Title:", "Key Components:", "## Heading")
        heading_split = re.split(
            r"(?=^(?:#{1,6}\s|(?:\d+\.|\*|\-)\s+[A-Z]))",
            para,
            flags=re.MULTILINE,
        )
        segments.extend(s.strip() for s in heading_split if s.strip())

    return segments


def merge_small_segments(segments: list[str], max_tokens: int) -> list[str]:
    """Merge consecutive small segments that fit within max_tokens."""
    merged = []
    buffer = ""

    for seg in segments:
        candidate = f"{buffer}\n\n{seg}".strip() if buffer else seg
        if estimate_tokens(candidate) <= max_tokens:
            buffer = candidate
        else:
            if buffer:
                merged.append(buffer)
            buffer = seg

    if buffer:
        merged.append(buffer)

    return merged


def sliding_window_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Fallback: split text using a sliding window over characters."""
    char_size = chunk_size * CHARS_PER_TOKEN
    char_overlap = overlap * CHARS_PER_TOKEN

    if len(text) <= char_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + char_size
        chunk = text[start:end]

        # Try to break at a sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            last_newline = chunk.rfind("\n")
            break_point = max(last_period, last_newline)
            if break_point > char_size // 2:
                chunk = text[start:start + break_point + 1]
                end = start + break_point + 1

        chunks.append(chunk.strip())
        start = end - char_overlap

    return [c for c in chunks if c]


def chunk_document(
    doc: dict,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict]:
    """Chunk a single document.

    Args:
        doc: Dict with at least 'source' and 'text' keys.
        chunk_size: Target chunk size in tokens.
        overlap: Overlap between chunks in tokens.

    Returns:
        List of chunk dicts with chunk_id, source, text, tokens.
    """
    text = doc["text"]
    source = doc.get("source", "unknown")

    # Try semantic splitting first
    segments = semantic_split(text)
    chunks_text = merge_small_segments(segments, chunk_size)

    # If any chunk is still too large, apply sliding window
    final_chunks = []
    for seg in chunks_text:
        if estimate_tokens(seg) > chunk_size * 1.5:
            final_chunks.extend(sliding_window_split(seg, chunk_size, overlap))
        else:
            final_chunks.append(seg)

    # Build output
    results = []
    for i, chunk_text in enumerate(final_chunks):
        tokens = estimate_tokens(chunk_text)
        if tokens < MIN_CHUNK_SIZE:
            continue
        results.append({
            "chunk_id": generate_chunk_id(source, i, chunk_text),
            "source": source,
            "text": chunk_text,
            "tokens": tokens,
            "page": doc.get("page", 1),
        })

    return results


def chunk_documents(
    documents: list[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict]:
    """Chunk a list of documents.

    Args:
        documents: List of dicts from ingest/clean pipeline.
        chunk_size: Target chunk size in tokens.
        overlap: Overlap between chunks in tokens.

    Returns:
        List of all chunks across all documents.
    """
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunk_document(doc, chunk_size, overlap))
    return all_chunks


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Chunk documents for study companion")
    parser.add_argument("input", help="Input JSONL file or '-' for stdin")
    parser.add_argument("--output", "-o", help="Output JSONL file (default: stdout)")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                        help=f"Target chunk size in tokens (default: {DEFAULT_CHUNK_SIZE})")
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP,
                        help=f"Overlap between chunks in tokens (default: {DEFAULT_OVERLAP})")
    args = parser.parse_args()

    # Read input
    if args.input == "-":
        lines = sys.stdin.read().strip().split("\n")
    else:
        lines = Path(args.input).read_text(encoding="utf-8").strip().split("\n")

    docs = [json.loads(line) for line in lines if line.strip()]
    chunks = chunk_documents(docs, args.chunk_size, args.overlap)

    output = "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Wrote {len(chunks)} chunks to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
